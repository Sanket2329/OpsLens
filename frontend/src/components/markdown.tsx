import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

export function Markdown({ content }: { content: string }) {
  return (
    <div className="prose prose-invert max-w-none text-sm prose-p:leading-relaxed prose-pre:border prose-pre:border-border prose-pre:bg-card-elevated prose-headings:text-foreground prose-code:text-foreground">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}