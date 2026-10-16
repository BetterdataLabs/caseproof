# Submission materials

The PDF and PowerPoint describe the development branch, including current document support. They contain placeholders for the hosted URL and access code. Insert those in your submission copy; keep credentials out of Git.

The deck generator uses PptxGenJS and no developer-specific files. Rebuild the PowerPoint from the repository root:

```bash
npm install --prefix /tmp/caseproof-deck --no-audit --no-fund pptxgenjs@4.0.1
NODE_PATH=/tmp/caseproof-deck/node_modules node docs/submission/build-deck.js
```

Export the generated PowerPoint to PDF with a presentation editor before submitting. When changing the slides, update both artifacts together.
