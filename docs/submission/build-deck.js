/**
 * Submission deck for the AI Builder Cup scoring round.
 * Rebuild: NODE_PATH=/tmp/caseproof-deck/node_modules node docs/submission/build-deck.js
 * Then replace the hosted URL on the last slide before exporting the PDF you upload.
 */
const path = require("path");
const pptxgen = require("pptxgenjs");

const THEME = {
  name: "CaseProof",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "112D3C",
    lt1: "FFFFFF",
    dk2: "18394B",
    lt2: "EEF4F1",
    accent1: "00675F",
    accent2: "18394B",
    accent3: "A86A12",
    accent4: "52656C",
    accent5: "1F6F78",
    accent6: "D8E2E0",
    hlink: "00675F",
    folHlink: "112D3C",
  },
};

const OUT = path.join(__dirname, "CaseProof-AI-Builder-Cup.pptx");

function text(slide, content, options) {
  slide.addText(content, {
    margin: 0,
    isTextBox: true,
    valign: "top",
    ...options,
  });
}

async function main() {
  const pres = new pptxgen();
  pres.defineLayout({ name: "DECK", width: 13.333, height: 7.5 });
  pres.layout = "DECK";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "CaseProof — AI Builder Cup 2026";
  pres.author = "CaseProof";
  pres.subject = "BFSI: Intelligent Risk, Fraud and Financial Experiences";
  pres.company = "CaseProof";
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "TITLE",
    background: { color: THEME.colors.dk1 },
    objects: [
      {
        text: {
          text: "CaseProof  ·  AI Builder Cup 2026  ·  BFSI",
          options: {
            x: 0.55,
            y: 7.05,
            w: 10.5,
            h: 0.28,
            fontSize: 12,
            color: "D8E2E0",
            margin: 0,
          },
        },
      },
    ],
    slideNumber: { x: 12.15, y: 7.05, w: 0.6, h: 0.28, color: "D8E2E0", fontSize: 12 },
  });

  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: "FFFFFF" },
    objects: [
      {
        placeholder: {
          options: {
            name: "title",
            type: "title",
            x: 0.55,
            y: 0.42,
            w: 12.2,
            h: 0.7,
            fontSize: 36,
            bold: true,
            color: C.text1,
            margin: 0,
            valign: "middle",
          },
          text: "Title",
        },
      },
      {
        text: {
          text: "CaseProof  ·  AI Builder Cup 2026  ·  BFSI",
          options: {
            x: 0.55,
            y: 7.05,
            w: 10.5,
            h: 0.28,
            fontSize: 12,
            color: "52656C",
            margin: 0,
          },
        },
      },
    ],
    slideNumber: { x: 12.15, y: 7.05, w: 0.6, h: 0.28, color: "52656C", fontSize: 12 },
  });

  function card(slide, x, y, w, h, name, fill = "EEF4F1") {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x,
      y,
      w,
      h,
      fill: { color: fill },
      rectRadius: 0.1,
      objectName: name,
    });
  }

  function badge(slide, x, y, n) {
    slide.addShape(pres.shapes.OVAL, {
      x,
      y,
      w: 0.38,
      h: 0.38,
      fill: { color: "00675F" },
      objectName: `Step ${n}`,
    });
    text(slide, String(n), {
      x,
      y,
      w: 0.38,
      h: 0.38,
      fontSize: 14,
      bold: true,
      color: "FFFFFF",
      align: "center",
      valign: "middle",
      objectName: `Step ${n} number`,
    });
  }

  pres.addSection({ title: "The problem" });
  pres.addSection({ title: "The product" });
  pres.addSection({ title: "Feasibility" });

  // 1. Title
  {
    const slide = pres.addSlide({ masterName: "TITLE", sectionTitle: "The problem" });
    text(slide, "AI BUILDER CUP 2026", {
      x: 0.7,
      y: 1.35,
      w: 11.5,
      h: 0.32,
      fontSize: 13,
      bold: true,
      color: "94CFC0",
      charSpacing: 1.5,
      objectName: "Eyebrow",
    });
    text(slide, "CaseProof", {
      x: 0.7,
      y: 1.75,
      w: 11.5,
      h: 0.95,
      fontSize: 60,
      bold: true,
      color: "FFFFFF",
      objectName: "Wordmark",
    });
    text(slide, "Invoice-financing document review", {
      x: 0.7,
      y: 2.75,
      w: 11.5,
      h: 0.45,
      fontSize: 24,
      color: "E6F4EF",
      objectName: "Product line",
    });
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.7,
      y: 3.5,
      w: 8.6,
      h: 0.58,
      fill: { color: "18394B" },
      rectRadius: 0.08,
      objectName: "Theme chip",
    });
    text(slide, "BFSI  ·  Intelligent Risk, Fraud & Financial Experiences", {
      x: 0.9,
      y: 3.58,
      w: 8.2,
      h: 0.42,
      fontSize: 16,
      color: "FFFFFF",
      valign: "middle",
      objectName: "Theme label",
    });
    text(
      slide,
      "Gemini reads the pack and plans the next request.\nThe bank still decides whether to finance.",
      {
        x: 0.7,
        y: 4.4,
        w: 10.5,
        h: 1.05,
        fontSize: 20,
        color: "E6F4EF",
        objectName: "Promise",
      },
    );
    const beats = ["Read the page", "Ask once", "Keep the file"];
    beats.forEach((label, i) => {
      const x = 0.7 + i * 3.5;
      text(slide, label, {
        x,
        y: 6.15,
        w: 3.2,
        h: 0.4,
        fontSize: 16,
        bold: true,
        color: "FFFFFF",
        objectName: label,
      });
    });
    slide.addNotes(
      "Open on the theme. CaseProof reviews invoice and receipt packs for a bank. Gemini proposes. The bank decides financing. Do not mention a fraud engine.",
    );
  }

  // 2. Problem
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The problem" });
    slide.addText("The file stalls in the gap", { placeholder: "title" });
    text(slide, "A mismatch is easy to spot.", {
      x: 0.55,
      y: 1.7,
      w: 5.5,
      h: 1.35,
      fontSize: 32,
      bold: true,
      color: C.text1,
      objectName: "Lead line",
    });
    text(slide, "The expensive part is asking once, recording the answer, and knowing what still blocks the file.", {
      x: 0.55,
      y: 3.25,
      w: 5.5,
      h: 2.4,
      fontSize: 20,
      color: C.text1,
      objectName: "Problem statement",
    });
    const points = [
      ["Disagree", "The invoice total and the delivery evidence do not match, or part of the delivery is missing."],
      ["Ask again", "The reviewer writes, waits, and writes again for whatever is still open."],
      ["No shared picture", "The business cannot see the block. The bank file cannot show how it cleared."],
    ];
    points.forEach(([title, body], i) => {
      const y = 1.45 + i * 1.84;
      card(slide, 6.4, y, 6.35, 1.54, title);
      text(slide, title, {
        x: 6.65,
        y: y + 0.22,
        w: 5.9,
        h: 0.38,
        fontSize: 20,
        bold: true,
        color: C.accent1,
        objectName: `${title} heading`,
      });
      text(slide, body, {
        x: 6.65,
        y: y + 0.68,
        w: 5.85,
        h: 0.72,
        fontSize: 15,
        color: C.text1,
        objectName: `${title} body`,
      });
    });
    slide.addNotes(
      "Name the user: a trade-operations reviewer on a sales-invoice financing file. The theme fit is automating that process, not a fraud product.",
    );
  }

  // 3. Who
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The product" });
    slide.addText("Three people, one file", { placeholder: "title" });
    const people = [
      ["Reviewer", "Sees the quote beside the field, the checklist, and one request. Records exceptions. Does not approve financing."],
      ["Submitting business", "Sends the invoice and receipts, answers that one request, and receives a document-review notice when the review is complete."],
      ["Bank file", "Keeps a frozen PDF and JSON. The client notice omits reviewer names, staff notes, and model traces."],
    ];
    people.forEach(([title, body], i) => {
      const x = 0.55 + i * 4.2;
      card(slide, x, 1.55, 3.95, 4.85, title);
      text(slide, title, {
        x: x + 0.28,
        y: 1.9,
        w: 3.44,
        h: 1.15,
        fontSize: 26,
        bold: true,
        color: C.text1,
        objectName: `${title} heading`,
      });
      text(slide, body, {
        x: x + 0.28,
        y: 3.25,
        w: 3.44,
        h: 2.7,
        fontSize: 16,
        color: C.text1,
        objectName: `${title} body`,
      });
    });
    slide.addNotes(
      "Alex handles bank review and administration, Sam is the submitting business, and Aisha can read the file. These are the three accounts in the submitted application.",
    );
  }

  // 4. Gemini vs code
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The product" });
    slide.addText("Gemini proposes. Code commits", { placeholder: "title" });
    card(slide, 0.55, 1.38, 6.0, 3.55, "Gemini column", "E6F4EF");
    card(slide, 6.75, 1.38, 6.0, 3.55, "Application column");
    text(slide, "Gemini on Vertex", {
      x: 0.82,
      y: 1.58,
      w: 5.45,
      h: 0.4,
      fontSize: 20,
      bold: true,
      color: C.accent1,
      objectName: "Gemini heading",
    });
    text(slide, "The application", {
      x: 7.02,
      y: 1.58,
      w: 5.45,
      h: 0.4,
      fontSize: 20,
      bold: true,
      color: C.text1,
      objectName: "Application heading",
    });
    const gemini = [
      "Proposes each field with its source quote",
      "Plans one request for every open gap",
      "Leaves a written dispute with a person",
      "Can review images and public evidence",
    ];
    const code = [
      "Commits arithmetic and delivery identity",
      "Holds a repeated seller invoice",
      "Owns tool scope, budget, and completion",
      "Leaves financing with the bank",
    ];
    text(
      slide,
      gemini.map((line, i) => ({ text: line, options: { bullet: true, breakLine: i < gemini.length - 1 } })),
      {
        x: 0.82,
        y: 2.15,
        w: 5.45,
        h: 2.5,
        fontSize: 16,
        color: C.text1,
        paraSpaceAfter: 10,
        objectName: "Gemini list",
      },
    );
    text(
      slide,
      code.map((line, i) => ({ text: line, options: { bullet: true, breakLine: i < code.length - 1 } })),
      {
        x: 7.02,
        y: 2.15,
        w: 5.45,
        h: 2.5,
        fontSize: 16,
        color: C.text1,
        paraSpaceAfter: 10,
        objectName: "Application list",
      },
    );
    card(slide, 0.55, 5.25, 12.2, 1.38, "Search boundary", "F4F7F5");
    text(slide, "Google Search, only when that case opts in", {
      x: 0.82,
      y: 5.4,
      w: 11.7,
      h: 0.36,
      fontSize: 16,
      bold: true,
      color: C.text1,
      objectName: "Search heading",
    });
    text(
      slide,
      "The call receives the company name, country, registration number, date, and a research angle. Invoice amounts, documents, messages, and case identifiers stay off it.",
      {
        x: 0.82,
        y: 5.8,
        w: 11.7,
        h: 0.7,
        fontSize: 15,
        color: C.text1,
        objectName: "Search body",
      },
    );
    slide.addNotes(
      "Model is gemini-3.8-flash through a bounded gateway. This is the Gen AI point: the model proposes evidence-linked work, and it cannot override the checks or approve a facility.",
    );
  }

  // 5. One case
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The product" });
    slide.addText("One case, end to end", { placeholder: "title" });
    const steps = [
      ["Vendor submits", "Invoice plus a receipt that covers only part of the delivery."],
      ["Checklist opens", "Wrong total and missing delivery, shown beside the source quote."],
      ["One request", "Both gaps go out together. The business is not asked twice."],
      ["Checklist closes", "The corrected invoice and the remaining receipt turn it green."],
      ["A person decides", "A dispute, or an instruction in the file, stays with the reviewer."],
      ["Two documents", "The vendor gets the client notice. The bank keeps the full summary."],
    ];
    steps.forEach(([title, body], i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const x = 0.55 + col * 4.18;
      const y = 1.42 + row * 2.72;
      card(slide, x, y, 3.88, 2.42, `Step card ${i + 1}`);
      badge(slide, x + 0.22, y + 0.24, i + 1);
      text(slide, title, {
        x: x + 0.72,
        y: y + 0.26,
        w: 3.05,
        h: 0.4,
        fontSize: 18,
        bold: true,
        color: C.text1,
        valign: "middle",
        objectName: `Step title ${i + 1}`,
      });
      text(slide, body, {
        x: x + 0.24,
        y: y + 0.9,
        w: 3.52,
        h: 1.35,
        fontSize: 15,
        color: C.text1,
        objectName: `Step body ${i + 1}`,
      });
    });
    slide.addNotes(
      "This is the video, in order. Sam then Alex. Cut the processing wait. Keep the Research page available for questions.",
    );
  }

  // 6. Cloud
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Feasibility" });
    slide.addText("Built to run on Cloud Run", { placeholder: "title" });
    const services = [
      ["Cloud Run", "Web, API, and worker as separate services"],
      ["Records", "Cloud SQL for the case. A private bucket for originals and summaries"],
      ["Delivery", "Cloud Tasks runs the worker. Cloud Scheduler reconciles"],
      ["Model", "Vertex AI Gemini, with Google ADK for the agent"],
    ];
    services.forEach(([title, body], i) => {
      const y = 1.38 + i * 1.32;
      card(slide, 0.55, y, 7.35, 1.16, title);
      text(slide, title, {
        x: 0.8,
        y: y + 0.16,
        w: 6.9,
        h: 0.36,
        fontSize: 18,
        bold: true,
        color: C.accent1,
        objectName: `${title} heading`,
      });
      text(slide, body, {
        x: 0.8,
        y: y + 0.56,
        w: 6.9,
        h: 0.46,
        fontSize: 15,
        color: C.text1,
        objectName: `${title} body`,
      });
    });
    card(slide, 8.1, 1.38, 4.65, 2.42, "Bounded", "E6F4EF");
    text(slide, "Already bounded", {
      x: 8.32,
      y: 1.56,
      w: 4.25,
      h: 0.36,
      fontSize: 18,
      bold: true,
      color: C.accent1,
      objectName: "Bounded heading",
    });
    text(slide, "Model work leaves the browser request. Originals are written once. Each case reserves cost and caps wakeups.", {
      x: 8.32,
      y: 2.08,
      w: 4.2,
      h: 1.55,
      fontSize: 15,
      color: C.text1,
      objectName: "Bounded body",
    });
    card(slide, 8.1, 4.12, 4.65, 2.38, "Prototype scope");
    text(slide, "Prototype, on purpose", {
      x: 8.32,
      y: 4.28,
      w: 4.25,
      h: 0.4,
      fontSize: 18,
      bold: true,
      color: C.text1,
      objectName: "Scope heading",
    });
    text(slide, "One demonstration organisation. PDFs, scans, images, DOCX, XLSX, CSV and text. Multiple items, currencies and taxes. Hosted demo access uses a code.", {
      x: 8.32,
      y: 4.82,
      w: 4.2,
      h: 1.55,
      fontSize: 15,
      color: C.text1,
      objectName: "Scope body",
    });
    slide.addNotes(
      "Feasibility slide. The topology is Cloud Run, Cloud SQL, Cloud Storage, Cloud Tasks, Scheduler, and Vertex. Say what is already bounded, then the document limit, so a judge who uploads a real tax invoice is not surprised.",
    );
  }

  // 7. Limits
  {
    const slide = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Feasibility" });
    slide.addText("Limits, stated up front", { placeholder: "title" });
    const limits = [
      ["Financing", "Does not approve, price, limit, or pay."],
      ["Screening", "Does not run sanctions, PEP, or adverse-media checks as a control."],
      ["Authenticity", "Does not prove a document is genuine, or verify legal identity."],
      ["Credit", "Does not score a company, or watch it over time."],
    ];
    limits.forEach(([title, body], i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = 0.55 + col * 6.4;
      const y = 1.4 + row * 1.78;
      card(slide, x, y, 6.15, 1.58, title);
      text(slide, title, {
        x: x + 0.28,
        y: y + 0.22,
        w: 5.6,
        h: 0.4,
        fontSize: 20,
        bold: true,
        color: C.text1,
        objectName: `${title} heading`,
      });
      text(slide, body, {
        x: x + 0.28,
        y: y + 0.75,
        w: 5.6,
        h: 0.7,
        fontSize: 16,
        color: C.text1,
        objectName: `${title} body`,
      });
    });
    card(slide, 0.55, 5.15, 12.2, 1.55, "Evidence", "E6F4EF");
    text(slide, "Evidence on this build", {
      x: 0.82,
      y: 5.32,
      w: 11.6,
      h: 0.34,
      fontSize: 16,
      bold: true,
      color: C.accent1,
      objectName: "Evidence heading",
    });
    text(
      slide,
      "60 constructed cases, 12 families, run on 12 October 2026. Zero incorrect completions on the agent and on the fixed-rule baseline. Staff minutes in that report are a time model, not a measured saving.",
      {
        x: 0.82,
        y: 5.8,
        w: 11.6,
        h: 0.78,
        fontSize: 15,
        color: C.text1,
        objectName: "Evidence body",
      },
    );
    slide.addNotes(
      "If asked whether the model beat a rules baseline: it matched the checklist. Say that only if asked. Do not present staff minutes as a saving. This is not a production error rate.",
    );
  }

  // 8. Open
  {
    const slide = pres.addSlide({ masterName: "TITLE", sectionTitle: "Feasibility" });
    text(slide, "Open the prototype", {
      x: 0.7,
      y: 0.55,
      w: 12,
      h: 0.7,
      fontSize: 36,
      bold: true,
      color: "FFFFFF",
      objectName: "Close title",
    });
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.7,
      y: 1.5,
      w: 11.9,
      h: 1.7,
      fill: { color: "FFFFFF" },
      rectRadius: 0.1,
      objectName: "URL card",
    });
    text(slide, "HOSTED URL  ·  REPLACE BEFORE YOU EXPORT THE PDF", {
      x: 0.98,
      y: 1.68,
      w: 11.3,
      h: 0.3,
      fontSize: 12,
      bold: true,
      color: "00675F",
      objectName: "URL label",
    });
    text(slide, "https://YOUR-CLOUD-RUN-HOST", {
      x: 0.98,
      y: 2.08,
      w: 11.3,
      h: 0.7,
      fontSize: 28,
      bold: true,
      color: "112D3C",
      objectName: "URL value",
    });
    const roles = [
      ["Vendor", "Submit the pack and reply"],
      ["Reviewer", "Quotes, checklist, decision"],
      ["Viewer", "Read the completed file"],
    ];
    roles.forEach(([title, body], i) => {
      const x = 0.7 + i * 4.05;
      slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x,
        y: 3.5,
        w: 3.85,
        h: 1.55,
        fill: { color: "18394B" },
        rectRadius: 0.1,
        objectName: `${title} role`,
      });
      text(slide, title, {
        x: x + 0.22,
        y: 3.68,
        w: 3.4,
        h: 0.4,
        fontSize: 18,
        bold: true,
        color: "FFFFFF",
        objectName: `${title} role heading`,
      });
      text(slide, body, {
        x: x + 0.22,
        y: 4.18,
        w: 3.4,
        h: 0.6,
        fontSize: 15,
        color: "E6F4EF",
        objectName: `${title} role body`,
      });
    });
    text(
      slide,
      "Access code: paste it on this line before you export the PDF. Put the same code on the submission form. Do not commit it.",
      {
        x: 0.7,
        y: 5.3,
        w: 11.9,
        h: 1.15,
        fontSize: 16,
        color: "E6F4EF",
        objectName: "Access note",
      },
    );
    slide.addNotes(
      "Last slide judges should remember. Paste the real Cloud Run URL over the placeholder. Paste the access code into this slide, then export the PDF you upload. Put the same URL and the same code on the form. Do not commit the code. Category on the form: BFSI, Intelligent Risk, Fraud and Financial Experiences. The dropdown's social-good labels are not this theme. After the code, the judge lands on a case that is already read. Client notice opens the completed example. Personas stay in the app.",
    );
  }

  await pres.writeFile({ fileName: OUT });
  console.log(OUT);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
