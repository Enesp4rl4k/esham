import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Rapor gövdesini (markdown) stilize edilmiş HTML'e çevirir.
 * @tailwindcss/typography eklentisine bağımlılığı önlemek için stiller
 * eleman bazında elle verilmiştir.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-zinc-300 leading-relaxed text-[17px]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => (
            <h1 className="text-3xl font-outfit font-bold text-white mt-10 mb-4" {...props} />
          ),
          h2: (props) => (
            <h2
              className="text-2xl font-outfit font-bold text-white mt-10 mb-4 border-b border-zinc-800 pb-2"
              {...props}
            />
          ),
          h3: (props) => (
            <h3 className="text-xl font-outfit font-semibold text-zinc-100 mt-8 mb-3" {...props} />
          ),
          p: (props) => <p className="mb-5" {...props} />,
          ul: (props) => <ul className="list-disc pl-6 mb-5 space-y-2" {...props} />,
          ol: (props) => <ol className="list-decimal pl-6 mb-5 space-y-2" {...props} />,
          li: (props) => <li className="marker:text-cyan-500" {...props} />,
          strong: (props) => <strong className="text-white font-semibold" {...props} />,
          a: (props) => (
            <a className="text-cyan-400 underline underline-offset-2 hover:text-cyan-300" {...props} />
          ),
          blockquote: (props) => (
            <blockquote
              className="border-l-2 border-cyan-700 pl-4 italic text-zinc-400 my-6"
              {...props}
            />
          ),
          code: (props) => (
            <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-sm text-cyan-300" {...props} />
          ),
          table: (props) => (
            <div className="overflow-x-auto my-6">
              <table className="w-full text-sm border border-zinc-800 rounded-lg" {...props} />
            </div>
          ),
          th: (props) => (
            <th className="text-left px-4 py-2 bg-zinc-900 border-b border-zinc-800 font-semibold text-zinc-200" {...props} />
          ),
          td: (props) => <td className="px-4 py-2 border-b border-zinc-800/60" {...props} />,
          hr: () => <hr className="border-zinc-800 my-8" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
