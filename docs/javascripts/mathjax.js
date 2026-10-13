// MathJax for the Markdown pages (pymdownx.arithmatex emits \( \) and \[ \]) and for the
// Markdown cells of the rendered notebooks ($...$ and $$...$$).
// Code (<pre>, <code>: MathJax default skipHtmlTags) and notebook code output
// (.jp-OutputArea, .jp-RenderedText) are not processed.
window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"], ["$", "$"]],
    displayMath: [["\\[", "\\]"], ["$$", "$$"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: "tex2jax_ignore|jp-OutputArea|jp-RenderedText",
  },
};

document$.subscribe(() => {
  MathJax.typesetPromise();
});
