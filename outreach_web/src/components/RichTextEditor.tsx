"use client";

import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import TextAlign from "@tiptap/extension-text-align";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { Bold, Italic, Underline as UnderlineIcon, AlignLeft, AlignCenter, AlignRight } from "lucide-react";
import { useEffect, useRef } from "react";

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  validVariables?: string[];
  onEditorReady?: (editor: Editor | null) => void;
  onBlur?: () => void;
  readOnly?: boolean;
}

const TEMPLATE_VARIABLE_PATTERN = /\{\{\s*([^{}]+?)\s*\}\}/g;

function normalizeTemplateVariable(variable: string): string {
  return variable.trim().replace(/\s+/g, "_");
}

const variableValidationPluginKey = new PluginKey<Set<string>>("variableValidation");

const VariableValidation = Extension.create({
  name: "variableValidation",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: variableValidationPluginKey,
        state: {
          init: () => new Set<string>(),
          apply(transaction, currentVariables) {
            const nextVariables = transaction.getMeta(variableValidationPluginKey) as string[] | undefined;
            return nextVariables ? new Set(nextVariables) : currentVariables;
          },
        },
        props: {
          decorations(state) {
            const validVariables = variableValidationPluginKey.getState(state) ?? new Set<string>();
            const decorations: Decoration[] = [];

            state.doc.descendants((node, position) => {
              if (!node.isText || !node.text) return;

              for (const match of node.text.matchAll(TEMPLATE_VARIABLE_PATTERN)) {
                const fullMatch = match[0];
                const variable = normalizeTemplateVariable(match[1]);

                if (validVariables.has(variable)) continue;

                const from = position + (match.index ?? 0);
                const to = from + fullMatch.length;
                decorations.push(
                  Decoration.inline(from, to, {
                    class: "template-variable-invalid",
                    title: `Unknown variable: ${variable}`,
                  })
                );
              }
            });

            return DecorationSet.create(state.doc, decorations);
          },
        },
      }),
    ];
  },
});

function ensureHTML(content: string): string {
  if (!content || /<[a-z][\s\S]*>/i.test(content)) return content;
  return content
    .split("\n\n")
    .map((para) => `<p>${para.replace(/\n/g, "<br>")}</p>`)
    .join("");
}

export default function RichTextEditor({ content, onChange, placeholder, validVariables = [], onEditorReady, onBlur, readOnly = false }: RichTextEditorProps) {
  const isUpdatingRef = useRef(false);

  const editor = useEditor({
    immediatelyRender: true,
    editable: !readOnly,
    extensions: [
      StarterKit.configure({
        heading: false,
        codeBlock: false,
        blockquote: false,
        horizontalRule: false,
        code: false,
      }),
      Placeholder.configure({
        placeholder: placeholder || "Compose your email...",
      }),
      TextAlign.configure({
        types: ["paragraph"],
      }),
      VariableValidation,
    ],
    content: content ? ensureHTML(content) : "",
    onCreate: ({ editor }) => {
      onEditorReady?.(editor);
    },
    onDestroy: () => {
      onEditorReady?.(null);
    },
    onUpdate: ({ editor }) => {
      if (!isUpdatingRef.current) {
        onChange(editor.getHTML());
      }
    },
    onBlur: () => {
      onBlur?.();
    },
    editorProps: {
      attributes: {
        class: "prose prose-sm max-w-none min-h-[320px] px-0 py-0 focus:outline-none text-slate-900 leading-relaxed",
      },
    },
  });

  useEffect(() => {
    onEditorReady?.(editor);
    return () => {
      onEditorReady?.(null);
    };
  }, [editor, onEditorReady]);

  useEffect(() => {
    if (!editor) return;
    const html = ensureHTML(content || "");
    if (editor.getHTML() !== html) {
      isUpdatingRef.current = true;
      editor.commands.setContent(html, { emitUpdate: false });
      isUpdatingRef.current = false;
    }
  }, [content, editor]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.view.dispatch(
      editor.state.tr.setMeta(
        variableValidationPluginKey,
        validVariables.map((variable) => normalizeTemplateVariable(variable))
      )
    );
  }, [editor, validVariables]);

  if (!editor) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b border-slate-100 bg-slate-50/50 select-none">
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive("bold")
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Bold"
        >
          <Bold className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive("italic")
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Italic"
        >
          <Italic className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive("underline")
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Underline"
        >
          <UnderlineIcon className="w-4 h-4" />
        </button>

        <div className="w-px h-4 bg-slate-200 mx-1" />

        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive({ textAlign: "left" })
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Align left"
        >
          <AlignLeft className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive({ textAlign: "center" })
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Align center"
        >
          <AlignCenter className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("right").run()}
          className={`p-1.5 rounded transition-colors cursor-pointer ${
            editor.isActive({ textAlign: "right" })
              ? "bg-slate-200 text-slate-800"
              : "hover:bg-slate-200/60 text-slate-500 hover:text-slate-800"
          }`}
          title="Align right"
        >
          <AlignRight className="w-4 h-4" />
        </button>
      </div>

      {/* Editor Content */}
      <div className="p-4 overflow-y-auto flex-1">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
