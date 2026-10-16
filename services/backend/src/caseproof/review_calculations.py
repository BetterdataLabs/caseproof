"""Exact, bounded arithmetic over explicitly cited document values."""

from __future__ import annotations

import ast
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Operand(BaseModel):
    name: str
    value: str = Field(
        description="Interpreted decimal value, using a dot, without currency or grouping marks."
    )
    raw: str = Field(
        description="Complete printed number, including original separators, signs and currency."
    )
    source_label: str
    page: int
    quote: str
    decimal_separator: Literal[".", ","] = Field(
        default=".", description="Decimal separator in the printed number: '.' or ','."
    )
    interpretation: str = Field(
        default="", description="Explain the source basis for locale, sign or other normalization."
    )

    @field_validator("decimal_separator", mode="before")
    @classmethod
    def normalise_separator(cls, value):
        return {"dot": ".", "comma": ","}.get(value, value) if isinstance(value, str) else value


class Calculation(BaseModel):
    id: str
    requirement_key: str
    description: str
    expression: str = Field(
        description="Use operand names or earlier calculation ids with +, -, *, / and parentheses. Only literal constants 0, 1 and 100 are allowed."
    )
    unit: str = Field(description="Currency or quantity unit; never combine incompatible units.")
    decimal_places: int | None = Field(
        default=None, description="Round only when justified by the document's stated precision."
    )
    rounding_method: Literal["half_up", "half_even", "half_down", "up", "down", "ceiling", "floor"] | None = (
        None
    )
    rounding_basis: str = ""
    expected_expression: str | None = Field(
        default=None,
        description="For a reconciliation, the independently stated amount or quantity to compare with expression.",
    )
    relation: Literal["eq", "ge", "le"] = "eq"
    scope: Literal[
        "calculation", "line_amount", "document_total", "delivery_quantity", "replacement_change"
    ] = "calculation"


class CalculationUncertainty(BaseModel):
    requirement_key: str
    detail: str


class CalculationPlan(BaseModel):
    operands: list[Operand] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    uncertainties: list[CalculationUncertainty] = Field(default_factory=list)


class OperandCitationCorrection(BaseModel):
    name: str = Field(description="Name of the existing operand whose quote needs repair.")
    source_label: str
    page: int
    quote: str = Field(min_length=3, max_length=800)


def repair_operand_citations(
    plan: CalculationPlan, corrections: list[OperandCitationCorrection], sources: list[dict]
) -> list[dict]:
    """Repair only a quotation on its original page; never substitute numbers or evidence."""
    by_label = {s["label"]: s for s in sources}
    by_name = {op.name: op for op in plan.operands}
    repairs = []
    repeated = {c.name for c in corrections if sum(other.name == c.name for other in corrections) > 1}
    for correction in corrections:
        operand = by_name.get(correction.name)
        if (
            not operand
            or correction.name in repeated
            or correction.source_label != operand.source_label
            or correction.page != operand.page
        ):
            continue
        source = by_label.get(operand.source_label)
        if not source:
            continue
        pages = source.get("pages") or [{"page": 1, "text": source["text"]}]
        text = next((p["text"] for p in pages if p["page"] == operand.page), "")
        if source_value_present(operand.raw, operand.quote, text):
            continue
        if not source_value_present(operand.raw, correction.quote, text):
            continue
        repairs.append({**correction.model_dump(), "previous_quote": operand.quote})
        operand.quote = correction.quote
    return repairs


def normalise(value: str) -> str:
    return " ".join(value.split())


def source_value_present(raw: str, quote: str, text: str) -> bool:
    """Match the complete source token, including signs outside a proposed quotation."""
    raw, quote, text = normalise(raw), normalise(quote), normalise(text)
    if not raw or not quote:
        return False
    numeric = any(c.isdigit() for c in raw)
    pattern = (
        re.compile(r"(?<![\w.,])" + re.escape(raw) + r"(?!\w|[.,]\d)")
        if numeric
        else re.compile(re.escape(raw))
    )
    for passage in re.finditer(re.escape(quote), text):
        for token in pattern.finditer(text, passage.start(), passage.end()):
            # Inspect the source, not just the model's potentially shortened quote.
            before, after = text[: token.start()], text[token.end() :]
            if numeric and (
                re.search(r"(?:[+\-−(]\s*(?:[^\W\d_]+(?:\s+[^\W\d_]+){0,2}|[^\w\s])?\s*)$", before)
                or re.match(r"\w|[.,]\d", after)
                or re.match(r"\s*[%)]", after)
                or re.match(r"-(?!\w)", after)
            ):
                continue
            return True
    return False


def printed_decimal(raw: str, separator: str) -> Decimal:
    if separator not in {".", ","}:
        raise ValueError("The numeric convention needs clarification.")
    cleaned = raw.replace("−", "-").strip()
    negative = cleaned.startswith("-") or ("(" in cleaned and ")" in cleaned) or cleaned.endswith("-")
    # Currency names and symbols carry no arithmetic meaning; preserve them in the cited operand.
    matches = re.findall(r"[+\-]?(?:\d[\d.,\s’']*\d|\d)(?:[eE][+\-]?\d+)?", cleaned)
    if len(matches) != 1:
        raise ValueError("The printed value needs an unambiguous numeric interpretation.")
    cleaned = re.sub(r"[\s’']", "", matches[0])
    grouping = "," if separator == "." else "."
    cleaned = cleaned.replace(grouping, "").replace(separator, ".")
    value = Decimal(cleaned)
    return -abs(value) if negative else value


def calculate(plan: CalculationPlan, sources: list[dict]) -> list[dict]:
    if len(plan.operands) > 500 or len(plan.calculations) > 300:
        raise ValueError("The numerical review must be split into smaller batches.")
    by_label = {source["label"]: source for source in sources}
    values, errors, origins, leaves = {}, {}, {}, {}
    for operand in plan.operands:
        try:
            if (
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,59}", operand.name)
                or operand.name in values
                or operand.name in errors
            ):
                raise ValueError("Operand names must be unique identifiers.")
            source = by_label.get(operand.source_label)
            if not source or not (
                (source["active"] and source["state"] == "ready") or source.get("usage") == "comparison_only"
            ):
                raise ValueError("Operand refers to unavailable evidence.")
            pages = source.get("pages") or [{"page": 1, "text": source["text"]}]
            text = next((p["text"] for p in pages if p["page"] == operand.page), "")
            quote, raw = normalise(operand.quote), normalise(operand.raw)
            if not quote or quote not in normalise(text):
                raise ValueError(
                    "The operand quote is not an exact passage on the cited page. Copy it verbatim from that page."
                )
            if not source_value_present(raw, quote, text):
                raise ValueError(
                    "Quote the complete source value, including signs, parentheses and separators."
                )
            value = Decimal(operand.value)
            if not value.is_finite() or len(operand.value) > 100 or abs(value.adjusted()) > 1000:
                raise ValueError("The interpreted operand is not a finite decimal.")
            signed = raw.replace("−", "-").strip()
            if value > 0 and (signed.startswith(("-", "(")) or signed.endswith("-")):
                raise ValueError("The interpreted value drops the printed negative sign.")
            if value < 0 and signed.startswith("+"):
                raise ValueError("The interpreted value contradicts the printed positive sign.")
            try:
                printed = printed_decimal(raw, operand.decimal_separator)
            except (ValueError, InvalidOperation):
                # Fractions, worded numbers and unfamiliar notation remain model interpretations,
                # explicitly explained and retained alongside the source, rather than admission failures.
                if not operand.interpretation.strip():
                    raise ValueError("Explain the source basis for this numeric interpretation.") from None
            else:
                if printed != value:
                    raise ValueError("The interpreted value does not match its printed numeric notation.")
            values[operand.name] = value
            origins[operand.name] = {operand.source_label}
            leaves[operand.name] = {operand.name}
        except (ValueError, InvalidOperation) as exc:
            errors[operand.name] = str(exc)
    results = []
    for calculation in plan.calculations:
        row = calculation.model_dump()
        try:
            if calculation.id in values or calculation.id in errors:
                raise ValueError("Calculation identifiers must be unique.")
            tree = ast.parse(calculation.expression, mode="eval")
            if len(calculation.expression) > 2000 or len(list(ast.walk(tree))) > 250:
                raise ValueError("Calculation is too large.")
            used = set()

            def evaluate(node, used=used):
                if isinstance(node, ast.Expression):
                    return evaluate(node.body)
                if isinstance(node, ast.Name):
                    if node.id in errors:
                        raise ValueError(errors[node.id])
                    if node.id not in values:
                        raise ValueError(f"No cited operand or calculation for {node.id}.")
                    used.add(node.id)
                    return values[node.id]
                if isinstance(node, ast.Constant) and type(node.value) is int and node.value in {0, 1, 100}:
                    return Decimal(node.value)
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    value = evaluate(node.operand)
                    return -value if isinstance(node.op, ast.USub) else value
                if isinstance(node, ast.BinOp):
                    left, right = evaluate(node.left), evaluate(node.right)
                    if isinstance(node.op, ast.Add):
                        return left + right
                    if isinstance(node.op, ast.Sub):
                        return left - right
                    if isinstance(node.op, ast.Mult):
                        return left * right
                    if isinstance(node.op, ast.Div):
                        return left / right
                raise ValueError("Use only cited operands and basic arithmetic.")

            with localcontext() as context:
                context.prec = 160
                context.Emax, context.Emin = 1000, -1000
                value = evaluate(tree)
                if not used:
                    raise ValueError("A calculation must use document evidence.")
                if calculation.decimal_places is not None:
                    if not 0 <= calculation.decimal_places <= 60:
                        raise ValueError("The requested calculation precision exceeds the tool limit.")
                    quantum = Decimal(1).scaleb(-calculation.decimal_places)
                    exact = value.quantize(quantum, rounding="ROUND_DOWN")
                    if exact == value:
                        value = exact  # Display precision alone needs no rounding assumption.
                    else:
                        if not calculation.rounding_method or not calculation.rounding_basis.strip():
                            raise ValueError(
                                "Specify the rounding method and its document basis; no default is assumed."
                            )
                        value = value.quantize(
                            quantum, rounding="ROUND_" + calculation.rounding_method.upper()
                        )
                if not value.is_finite():
                    raise ValueError("Calculation is not finite.")
                if calculation.expected_expression is not None:
                    if calculation.scope == "document_total" and calculation.relation != "eq":
                        raise ValueError("An invoice total reconciliation must compare equal amounts.")
                    left_used = set(used)
                    used.clear()
                    if len(calculation.expected_expression) > 2000:
                        raise ValueError("Comparison is too large.")
                    expected_tree = ast.parse(calculation.expected_expression, mode="eval")
                    if len(list(ast.walk(expected_tree))) > 250:
                        raise ValueError("Comparison is too large.")
                    expected = evaluate(expected_tree)
                    if calculation.scope == "document_total" and not used:
                        raise ValueError(
                            "A reconciliation must compare against independently cited evidence."
                        )
                    if calculation.scope == "document_total" and set().union(
                        *(leaves[n] for n in left_used)
                    ) == set().union(*(leaves[n] for n in used)):
                        raise ValueError("An invoice total cannot be verified by comparing it with itself.")
                    used.update(left_used)
                    matched = {"eq": value == expected, "ge": value >= expected, "le": value <= expected}[
                        calculation.relation
                    ]
                    row.update(
                        expected_result=format(expected, "f"),
                        difference=format(value - expected, "f"),
                        comparison="matched" if matched else "mismatch",
                    )
            values[calculation.id] = value
            origins[calculation.id] = set().union(*(origins[name] for name in used))
            leaves[calculation.id] = set().union(*(leaves[name] for name in used))
            historical = {
                label
                for label in origins[calculation.id]
                if by_label[label].get("usage") == "comparison_only"
            }
            comparison_only = bool(historical) and historical == origins[calculation.id]
            if (
                calculation.scope in {"document_total", "delivery_quantity"}
                and historical
                and not comparison_only
            ):
                raise ValueError(
                    "Previous versions provide comparison context, not current invoice or delivery totals."
                )
            row.update(
                result=format(value, "f"),
                status="calculated",
                operands=sorted(used),
                source_labels=sorted(origins[calculation.id]),
                usage="comparison_only" if comparison_only else "current_evidence",
            )
        except (ValueError, ArithmeticError, SyntaxError, RecursionError) as exc:
            errors[calculation.id] = str(exc)
            row.update(status="review_required", error=str(exc))
        results.append(row)
    return results
