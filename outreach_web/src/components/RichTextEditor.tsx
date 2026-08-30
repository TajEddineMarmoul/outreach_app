"use client";

import {
  useEditor,
  useEditorState,
  EditorContent,
  type Editor,
} from "@tiptap/react";
import { Extension } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import TextAlign from "@tiptap/extension-text-align";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Link as LinkIcon,
  List,
  ListOrdered,
  Undo2,
  Redo2,
  Braces,
  AlignLeft,
  AlignCenter,
  AlignRight,
  ChevronDown,
} from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useEffect, useId, useRef, useState } from "react";
import "@/components/campaigns/workspace/campaign-workspace.css";
import {
  TEMPLATE_VARIABLE_PATTERN,
  templateVariableName,
} from "@/lib/templateVariables";

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  validVariables?: string[];
  onEditorReady?: (editor: Editor | null) => void;
  onBlur?: () => void;
  readOnly?: boolean;
  onInsertVariable?: () => void;
  minimalToolbar?: boolean;
}

const variableValidationPluginKey = new PluginKey<Set<string>>(
  "variableValidation",
);

const VariableValidation = Extension.create({
  name: "variableValidation",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: variableValidationPluginKey,
        state: {
          init: () => new Set<string>(),
          apply(transaction, currentVariables) {
            const nextVariables = transaction.getMeta(
              variableValidationPluginKey,
            ) as string[] | undefined;
            return nextVariables ? new Set(nextVariables) : currentVariables;
          },
        },
        props: {
          decorations(state) {
            const validVariables =
              variableValidationPluginKey.getState(state) ?? new Set<string>();
            const decorations: Decoration[] = [];

            state.doc.descendants((node, position) => {
              if (!node.isText || !node.text) return;

              for (const match of node.text.matchAll(
                TEMPLATE_VARIABLE_PATTERN,
              )) {
                const fullMatch = match[0];
                const variable = templateVariableName(match[1]);

                const from = position + (match.index ?? 0);
                const to = from + fullMatch.length;
                decorations.push(
                  Decoration.inline(from, to, {
                    class: validVariables.has(variable)
                      ? "template-variable-valid"
                      : "template-variable-invalid",
                    title: validVariables.has(variable)
                      ? `Personalized for each recipient: ${variable}`
                      : `Unknown variable: ${variable}`,
                  }),
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

export default function RichTextEditor({
  content,
  onChange,
  placeholder,
  validVariables = [],
  onEditorReady,
  onBlur,
  readOnly = false,
  onInsertVariable,
  minimalToolbar = false,
}: RichTextEditorProps) {
  const isUpdatingRef = useRef(false);
  const [formattingOpen, setFormattingOpen] = useState(false);
  const toolbarId = useId();

  const editor = useEditor({
    immediatelyRender: false,
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
        role: "textbox",
        "aria-label": "Email message",
        "aria-multiline": "true",
        class:
          "prose prose-sm max-w-none min-h-[320px] px-0 py-0 focus:outline-none text-slate-900 leading-relaxed",
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
    editor.setEditable(!readOnly, false);
  }, [editor, readOnly]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.view.dispatch(
      editor.state.tr.setMeta(
        variableValidationPluginKey,
        validVariables.map((variable) => templateVariableName(variable)),
      ),
    );
  }, [editor, validVariables]);

  const toolbar = useEditorState({
    editor,
    selector: ({ editor }) =>
      editor
        ? {
            bold: editor.isActive("bold"),
            italic: editor.isActive("italic"),
            underline: editor.isActive("underline"),
            link: editor.isActive("link"),
            bulletList: editor.isActive("bulletList"),
            orderedList: editor.isActive("orderedList"),
            canUndo: editor.can().undo(),
            canRedo: editor.can().redo(),
          }
        : null,
  });

  if (!editor)
    return (
      <div className="campaign-editor-loading min-h-[380px]" aria-label="Loading message editor" />
    );
  const addLink = () => {
    const value = window.prompt(
      "Link URL (https://…)",
      editor.getAttributes("link").href || "https://",
    );
    if (value === null) return;
    if (!value.trim()) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    try {
      const url = new URL(value);
      if (!["https:", "http:", "mailto:"].includes(url.protocol))
        throw new Error();
      editor
        .chain()
        .focus()
        .extendMarkRange("link")
        .setLink({ href: url.href })
        .run();
    } catch {
      window.alert("Enter a valid https, http, or mailto link.");
    }
  };
  const controls = [
    {
      label: "Bold",
      icon: Bold,
      active: toolbar?.bold,
      run: () => editor.chain().focus().toggleBold().run(),
    },
    {
      label: "Italic",
      icon: Italic,
      active: toolbar?.italic,
      run: () => editor.chain().focus().toggleItalic().run(),
    },
    {
      label: "Underline",
      icon: UnderlineIcon,
      active: toolbar?.underline,
      run: () => editor.chain().focus().toggleUnderline().run(),
    },
    {
      label: "Insert link",
      icon: LinkIcon,
      active: toolbar?.link,
      run: addLink,
    },
    {
      label: "Bullet list",
      icon: List,
      active: toolbar?.bulletList,
      run: () => editor.chain().focus().toggleBulletList().run(),
    },
    {
      label: "Numbered list",
      icon: ListOrdered,
      active: toolbar?.orderedList,
      run: () => editor.chain().focus().toggleOrderedList().run(),
    },
  ];
  return (
    <div className="flex flex-col h-full">
      {minimalToolbar && (
        <div className="campaign-editor-topline">
          <span>Message</span>
          {!readOnly && (
            <button type="button" className="campaign-text-button" aria-expanded={formattingOpen} aria-controls={toolbarId} onClick={() => setFormattingOpen(!formattingOpen)}>
              Formatting <ChevronDown size={14} />
            </button>
          )}
        </div>
      )}
      {(!minimalToolbar || formattingOpen) && (
      <div
        id={toolbarId}
        className="campaign-rich-toolbar"
        role="group"
        aria-label="Message formatting"
      >
        <Popover>
          <PopoverTrigger
            className="campaign-toolbar-format"
            aria-label="Paragraph alignment"
            disabled={readOnly}
          >
            <span>Paragraph</span>
            <ChevronDown size={13} />
          </PopoverTrigger>
          <PopoverContent align="start" className="campaign-ui w-44">
            {(
              [
                { value: "left", icon: AlignLeft },
                { value: "center", icon: AlignCenter },
                { value: "right", icon: AlignRight },
              ] as const
            ).map(({ value, icon: Icon }) => (
              <button
                key={value}
                type="button"
                className="campaign-text-button justify-start px-2 capitalize"
                onClick={() => editor.chain().focus().setTextAlign(value).run()}
              >
                <Icon size={17} />
                Align {value}
              </button>
            ))}
          </PopoverContent>
        </Popover>
        <span className="campaign-toolbar-divider" />
        {controls.map(({ label, icon: Icon, active, run }) => (
          <button
            key={label}
            type="button"
            title={label}
            aria-label={label}
            aria-pressed={Boolean(active)}
            disabled={readOnly}
            onClick={run}
          >
            <Icon />
          </button>
        ))}
        {onInsertVariable && (
          <button
            type="button"
            title="Insert personalization"
            aria-label="Insert personalization"
            disabled={readOnly}
            onClick={onInsertVariable}
          >
            <Braces />
          </button>
        )}
        <span className="campaign-toolbar-spacer" />
        <button
          type="button"
          title="Undo"
          aria-label="Undo"
          disabled={readOnly || !toolbar?.canUndo}
          onClick={() => editor.chain().focus().undo().run()}
        >
          <Undo2 />
        </button>
        <button
          type="button"
          title="Redo"
          aria-label="Redo"
          disabled={readOnly || !toolbar?.canRedo}
          onClick={() => editor.chain().focus().redo().run()}
        >
          <Redo2 />
        </button>
      </div>
      )}
      <div className="campaign-rich-body p-4 overflow-y-auto flex-1">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
