import MarkdownIt from "markdown-it";

type SimpleMarkdownRenderOptions = {
  emptyHtml?: string;
};

const renderer = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
});

export function renderSimpleMarkdown(source: string | null | undefined, options: SimpleMarkdownRenderOptions = {}): string {
  const text = String(source || "").trim();
  if (!text) return options.emptyHtml || "";
  return renderer.render(text);
}
