export function ScenarioGuide({ steps }: { steps?: string[] }) {
  if (!steps?.length) return null;
  return (
    <details className="rounded-xl border border-line bg-paper px-4 py-3">
      <summary className="cursor-pointer text-[13px] font-semibold text-teal-800">
        How to run this example
      </summary>
      <ol className="mt-3 list-decimal space-y-2 pl-4 text-[12.5px] leading-relaxed text-muted">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <a
        className="mt-3 inline-block text-[12.5px] font-semibold text-teal-700 underline underline-offset-2"
        href="/sample-documents/scenarios/index.html"
        target="_blank"
        rel="noreferrer"
      >
        Browse the document testing library
      </a>
    </details>
  );
}
