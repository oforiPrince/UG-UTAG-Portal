"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  Bold,
  Braces,
  Code2,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Pilcrow,
  Quote,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Underline,
  Undo2,
  Unlink,
} from "lucide-react";
import { type ComponentType, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { normalizeEditorHtml, normalizeLinkHref } from "@/lib/rich-text";
import { cn } from "@/lib/utils";

type RichTextEditorProps = {
  id: string;
  labelledBy: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
};

type ToolbarButtonProps = {
  label: string;
  icon: ComponentType<{ className?: string }>;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
};

function ToolbarButton({
  label,
  icon: Icon,
  active,
  disabled = false,
  onClick,
}: ToolbarButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active === undefined ? undefined : active}
      disabled={disabled}
      title={label}
      onClick={onClick}
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-ink/[.07] hover:text-ink disabled:cursor-not-allowed disabled:opacity-35",
        active && "bg-sky/12 text-sky ring-1 ring-ink/10",
      )}
    >
      <Icon className="size-4" />
    </button>
  );
}

function ToolbarDivider() {
  return <span aria-hidden="true" className="mx-0.5 h-6 w-px bg-line" />;
}

export function RichTextEditor({
  id,
  labelledBy,
  value,
  onChange,
  placeholder = "Start writing…",
  required = false,
}: RichTextEditorProps) {
  const onChangeRef = useRef(onChange);
  const lastEmittedValueRef = useRef(value);
  const linkInputRef = useRef<HTMLInputElement>(null);
  const [linkEditorOpen, setLinkEditorOpen] = useState(false);
  const [linkValue, setLinkValue] = useState("");
  const [linkError, setLinkError] = useState("");

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const editor = useEditor({
    immediatelyRender: false,
    content: value,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        link: {
          autolink: true,
          defaultProtocol: "https",
          enableClickSelection: true,
          HTMLAttributes: {
            rel: "noopener noreferrer",
            target: "_blank",
          },
          linkOnPaste: true,
          openOnClick: false,
          protocols: ["http", "https", "mailto"],
        },
      }),
      Placeholder.configure({ placeholder }),
    ],
    editorProps: {
      attributes: {
        "aria-labelledby": labelledBy,
        "aria-multiline": "true",
        "aria-required": required ? "true" : "false",
        class: "rich-text-content",
        id,
        role: "textbox",
        spellcheck: "true",
      },
    },
    onUpdate: ({ editor: currentEditor }) => {
      const nextValue = normalizeEditorHtml(currentEditor.getHTML());
      lastEmittedValueRef.current = nextValue;
      onChangeRef.current(nextValue);
    },
  });

  useEffect(() => {
    if (!editor || value === lastEmittedValueRef.current) return;
    lastEmittedValueRef.current = value;
    editor.commands.setContent(value, { emitUpdate: false });
  }, [editor, value]);

  useEffect(() => {
    if (!linkEditorOpen) return;
    linkInputRef.current?.focus();
  }, [linkEditorOpen]);

  if (!editor) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading rich text editor"
        className="grid min-h-72 place-items-center rounded-xl border border-line bg-panel text-xs font-normal text-muted"
      >
        Preparing editor…
      </div>
    );
  }

  const selectionIsEmpty = editor.state.selection.empty;
  const wordCount = editor.getText().trim().split(/\s+/).filter(Boolean).length;

  function openLinkEditor() {
    const currentHref = String(editor?.getAttributes("link").href ?? "");
    setLinkValue(currentHref);
    setLinkError("");
    setLinkEditorOpen(true);
  }

  function applyLink() {
    if (!editor) return;

    const href = normalizeLinkHref(linkValue);
    if (href === null) {
      setLinkError("Enter a valid website address or email address.");
      return;
    }

    if (!href) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    }
    setLinkEditorOpen(false);
    setLinkError("");
  }

  return (
    <div className="overflow-clip rounded-xl border border-line bg-paper shadow-[0_8px_28px_rgb(23_43_69_/_6%)] focus-within:border-ink/25 focus-within:ring-0">
      <div
        aria-label="Text formatting"
        role="toolbar"
        className="sticky top-0 z-20 flex flex-wrap items-center gap-0.5 border-b border-line bg-panel/95 p-2 backdrop-blur"
      >
        <select
          aria-label="Text style"
          title="Text style"
          value={
            editor.isActive("heading", { level: 2 })
              ? "heading-2"
              : editor.isActive("heading", { level: 3 })
                ? "heading-3"
                : editor.isActive("heading", { level: 4 })
                  ? "heading-4"
                  : "paragraph"
          }
          onChange={(event) => {
            const command = editor.chain().focus();
            const style = event.target.value;
            if (style === "heading-2") command.setHeading({ level: 2 }).run();
            else if (style === "heading-3")
              command.setHeading({ level: 3 }).run();
            else if (style === "heading-4")
              command.setHeading({ level: 4 }).run();
            else command.setParagraph().run();
          }}
          className="mr-1 h-9 min-w-28 rounded-lg border border-line bg-paper px-2 text-xs font-bold text-ink outline-none focus:border-ink/25"
        >
          <option value="paragraph">Paragraph</option>
          <option value="heading-2">Heading 2</option>
          <option value="heading-3">Heading 3</option>
          <option value="heading-4">Heading 4</option>
        </select>

        <ToolbarButton
          label="Bold (⌘B)"
          icon={Bold}
          active={editor.isActive("bold")}
          onClick={() => editor.chain().focus().toggleBold().run()}
        />
        <ToolbarButton
          label="Italic (⌘I)"
          icon={Italic}
          active={editor.isActive("italic")}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        />
        <ToolbarButton
          label="Underline (⌘U)"
          icon={Underline}
          active={editor.isActive("underline")}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
        />
        <ToolbarButton
          label="Strike through"
          icon={Strikethrough}
          active={editor.isActive("strike")}
          onClick={() => editor.chain().focus().toggleStrike().run()}
        />
        <ToolbarButton
          label="Inline code"
          icon={Code2}
          active={editor.isActive("code")}
          onClick={() => editor.chain().focus().toggleCode().run()}
        />

        <ToolbarDivider />

        <ToolbarButton
          label="Bullet list"
          icon={List}
          active={editor.isActive("bulletList")}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        />
        <ToolbarButton
          label="Numbered list"
          icon={ListOrdered}
          active={editor.isActive("orderedList")}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        />
        <ToolbarButton
          label="Block quote"
          icon={Quote}
          active={editor.isActive("blockquote")}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
        />
        <ToolbarButton
          label="Code block"
          icon={Braces}
          active={editor.isActive("codeBlock")}
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        />
        <ToolbarButton
          label="Horizontal divider"
          icon={Minus}
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
        />

        <ToolbarDivider />

        <ToolbarButton
          label={
            selectionIsEmpty && !editor.isActive("link")
              ? "Select text to add a link"
              : "Add or edit link"
          }
          icon={Link2}
          active={editor.isActive("link")}
          disabled={selectionIsEmpty && !editor.isActive("link")}
          onClick={openLinkEditor}
        />
        <ToolbarButton
          label="Remove link"
          icon={Unlink}
          disabled={!editor.isActive("link")}
          onClick={() =>
            editor.chain().focus().extendMarkRange("link").unsetLink().run()
          }
        />
        <ToolbarButton
          label="Clear formatting"
          icon={RemoveFormatting}
          onClick={() =>
            editor.chain().focus().clearNodes().unsetAllMarks().run()
          }
        />

        <span className="grow" />

        <ToolbarButton
          label="Undo (⌘Z)"
          icon={Undo2}
          disabled={!editor.can().chain().focus().undo().run()}
          onClick={() => editor.chain().focus().undo().run()}
        />
        <ToolbarButton
          label="Redo (⇧⌘Z)"
          icon={Redo2}
          disabled={!editor.can().chain().focus().redo().run()}
          onClick={() => editor.chain().focus().redo().run()}
        />
      </div>

      {linkEditorOpen ? (
        <div
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.stopPropagation();
              applyLink();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              setLinkEditorOpen(false);
              setLinkError("");
              editor.chain().focus().run();
            }
          }}
          className="grid gap-2 border-b border-line bg-sky/[.055] p-3 sm:grid-cols-[1fr_auto]"
        >
          <div className="grid gap-1">
            <label htmlFor={`${id}-link`} className="text-[.68rem] font-bold">
              Link address
            </label>
            <input
              ref={linkInputRef}
              id={`${id}-link`}
              value={linkValue}
              inputMode="url"
              placeholder="https://example.com or name@example.com"
              onChange={(event) => {
                setLinkValue(event.target.value);
                setLinkError("");
              }}
              className="min-h-10 rounded-lg border border-line bg-paper px-3 text-xs font-normal outline-none focus:border-ink/25"
            />
            {linkError ? (
              <span
                role="alert"
                className="font-normal text-red-700 dark:text-red-300"
              >
                {linkError}
              </span>
            ) : null}
          </div>
          <div className="flex items-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setLinkEditorOpen(false);
                setLinkError("");
                editor.chain().focus().run();
              }}
            >
              Cancel
            </Button>
            <Button type="button" size="sm" onClick={applyLink}>
              Apply link
            </Button>
          </div>
        </div>
      ) : null}

      <EditorContent editor={editor} />

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line bg-panel/60 px-3 py-2 text-[.68rem] font-normal text-muted">
        <span className="flex items-center gap-1.5">
          <Pilcrow className="size-3.5" aria-hidden="true" />
          Rich text · formatting is preserved
        </span>
        <span aria-live="polite">
          {wordCount} {wordCount === 1 ? "word" : "words"}
        </span>
      </div>
    </div>
  );
}
