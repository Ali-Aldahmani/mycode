import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import type { CodeRange } from "@/engine/frames";

type MonacoEditor = Parameters<OnMount>[0];
type Monaco = Parameters<OnMount>[1];

interface Props {
  value: string;
  onChange?: (v: string) => void;
  /** Range of the stage currently playing. */
  highlight?: CodeRange | null;
  errorLine?: number | null;
  readOnly?: boolean;
  /** Ctrl/Cmd+Enter. */
  onSubmit?: () => void;
  height?: string | number;
  language?: string;
}

function defineTheme(monaco: Monaco) {
  monaco.editor.defineTheme("trainer-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "string", foreground: "f5c287" },
      { token: "keyword", foreground: "c792ea" },
      { token: "number", foreground: "f78c6c" },
      { token: "comment", foreground: "6a737d", fontStyle: "italic" },
    ],
    colors: {
      "editor.background": "#1e1e1e",
      "editor.lineHighlightBackground": "#262626",
      "editorLineNumber.foreground": "#555555",
      "editorLineNumber.activeForeground": "#a3a3a3",
      "editorGutter.background": "#1e1e1e",
    },
  });
}

export function CodeEditor({ value, onChange, highlight, errorLine, readOnly, onSubmit, height = "100%", language = "python" }: Props) {
  const editorRef = useRef<MonacoEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const decorations = useRef<string[]>([]);
  const submitRef = useRef(onSubmit);
  submitRef.current = onSubmit;

  const onMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => submitRef.current?.());
    paint();
  };

  const paint = () => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;
    const next: Parameters<MonacoEditor["deltaDecorations"]>[1] = [];
    if (highlight) {
      next.push({
        range: new monaco.Range(highlight.startLine, highlight.startCol, highlight.endLine, highlight.endCol),
        options: { inlineClassName: "code-stage-highlight" },
      });
    }
    if (errorLine) {
      next.push({
        range: new monaco.Range(errorLine, 1, errorLine, 1),
        options: { isWholeLine: true, className: "code-error-line", glyphMarginClassName: "code-error-glyph" },
      });
    }
    decorations.current = editor.deltaDecorations(decorations.current, next);
  };

  useEffect(paint, [highlight, errorLine]);

  return (
    <Editor
      height={height}
      language={language}
      value={value}
      theme="trainer-dark"
      beforeMount={defineTheme}
      onMount={onMount}
      onChange={(v) => onChange?.(v ?? "")}
      loading={<div className="p-4 text-sm text-neutral-500">Loading editor…</div>}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 14,
        fontFamily: "'JetBrains Mono', ui-monospace, Consolas, monospace",
        lineHeight: 22,
        scrollBeyondLastLine: false,
        padding: { top: 12, bottom: 12 },
        glyphMargin: true,
        lineNumbersMinChars: 3,
        renderLineHighlight: "line",
        tabSize: 4,
        automaticLayout: true,
        overviewRulerLanes: 0,
        scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
      }}
    />
  );
}
