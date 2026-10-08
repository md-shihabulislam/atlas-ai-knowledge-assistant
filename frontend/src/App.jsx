
import React, { useEffect, useRef, useState } from "react";

import {
  BookOpen,
  ChevronRight,
  CircleHelp,
  CloudUpload,
  Database,
  FileText,
  Layers2,
  Menu,
  Plus,
  Search,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

// Backend API configuration
const API = (
  import.meta.env.VITE_API_BASE || "http://localhost:8000"
).replace(/\/+$/, "");

const examples = [
  "How many days of annual leave are provided?",
  "What is the remote work policy?",
  "When do expenses require approval?",
];

// API request helper
async function request(path, init = {}) {
  let response;

  try {
    response = await fetch(`${API}${path}`, init);
  } catch {
    throw new Error(
      "Cannot reach the backend. Start the API at http://localhost:8000."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`
    );
  }

  return data;
}

// Source reference component
function SourceCard({ source }) {
  const content = source.content || "";
  const score = Number(source.score || 0);

  return (
    <div className="source-card">
      <div className="source-heading">
        <span className="source-number">{source.id}</span>

        <div className="source-meta">
          <strong title={source.filename}>
            {source.filename}
          </strong>

          <span>
            Page {source.page ?? "N/A"} · relevance{" "}
            {Math.round(score * 100)}%
          </span>
        </div>
      </div>

      <p>
        {content.length > 320
          ? content.slice(0, 320) + "…"
          : content}
      </p>
    </div>
  );
}

// Main application
export default function App() {
  const [docs, setDocs] = useState([]);
  const [health, setHealth] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");

  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const [error, setError] = useState("");
  const [showMobile, setShowMobile] = useState(false);

  const inputRef = useRef(null);
  const bottomRef = useRef(null);

  // Initial backend connection
  useEffect(() => {
    request("/api/health")
      .then(setHealth)
      .catch((e) => setError(e.message));

    request("/api/documents")
      .then((data) => setDocs(data.documents || []))
      .catch((e) => setError(e.message));
  }, []);

  // Automatically scroll to the latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, busy]);

  // Upload PDF or TXT documents
  async function upload(file) {
    if (!file || uploading) return;

    if (!/\.(txt|pdf)$/i.test(file.name)) {
      setError("Upload a PDF or .txt document.");
      return;
    }

    if (file.size > 8 * 1024 * 1024) {
      setError("Maximum file size is 8 MB.");
      return;
    }

    setError("");
    setUploading(true);

    try {
      const form = new FormData();
      form.append("file", file);

      await request("/api/documents", {
        method: "POST",
        body: form,
      });

      const updated = await request("/api/documents");

      setDocs(updated.documents || []);
      setShowMobile(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);

      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  // Remove a document
  async function remove(doc) {
    const confirmed = window.confirm(
      `Remove ${doc.filename} from this knowledge base?`
    );

    if (!confirmed) return;

    setError("");

    try {
      await request(`/api/documents/${doc.id}`, {
        method: "DELETE",
      });

      setDocs((old) =>
        old.filter((item) => item.id !== doc.id)
      );
    } catch (e) {
      setError(e.message);
    }
  }

  // Ask the knowledge assistant
  async function ask(text) {
    const q = (text ?? question).trim();

    if (!q || busy || docs.length === 0) return;

    setQuestion("");
    setError("");
    setBusy(true);

    setMessages((old) => [
      ...old,
      {
        role: "user",
        content: q,
      },
    ]);

    try {
      const result = await request("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: q,
        }),
      });

      setMessages((old) => [
        ...old,
        {
          ...result,
          role: "assistant",
        },
      ]);
    } catch (e) {
      setError(e.message);

      setMessages((old) => [
        ...old,
        {
          role: "assistant",
          answer: "Sorry, I could not complete that request.",
          sources: [],
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  // Handle drag-and-drop document uploading
  function dragUpload(e) {
    e.preventDefault();
    setDragging(false);

    const file = e.dataTransfer?.files?.[0];

    if (file) {
      upload(file);
    }
  }

  return (
    <div className="app-shell">

      {/* SIDEBAR */}
      <aside className={`sidebar ${showMobile ? "open" : ""}`}>

        {/* Brand */}
        <div className="brand">
          <div className="brand-icon">
            <Layers2 size={20} />
          </div>

          <div>
            <strong>
              atlas<span className="dot">.</span>
            </strong>

            <small>KNOWLEDGE AI</small>
          </div>

          <button
            className="mobile-close"
            onClick={() => setShowMobile(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <div className="nav-heading">
          WORKSPACE
        </div>

        <div className="nav-item selected">
          <BookOpen size={17} />
          Knowledge assistant

          <ChevronRight
            size={16}
            className="nav-chevron"
          />
        </div>

        {/* Knowledge base */}
        <div className="library-header">
          <span>KNOWLEDGE BASE</span>

          <span className="count-pill">
            {docs.length}
          </span>
        </div>

        {/* Upload zone */}
        <div
          className={`upload-zone ${
            dragging ? "dragging" : ""
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={dragUpload}
          onClick={() => {
            if (!uploading) {
              inputRef.current?.click();
            }
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (
              (e.key === "Enter" || e.key === " ") &&
              !uploading
            ) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
        >
          <div className="upload-icon">
            <CloudUpload size={22} />
          </div>

          <strong>
            {uploading
              ? "Indexing document…"
              : "Upload a document"}
          </strong>

          <span>
            Click or drop PDF / TXT
          </span>

          <small>
            Up to 8 MB · 50 pages
          </small>

          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            hidden
            disabled={uploading}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              upload(e.target.files?.[0]);
            }}
          />
        </div>

        {/* Uploaded documents */}
        <div className="files-list">
          {docs.map((doc) => (
            <div
              className="file-item"
              key={doc.id}
            >
              <div className="file-icon">
                <FileText size={18} />
              </div>

              <div className="file-info">
                <strong title={doc.filename}>
                  {doc.filename}
                </strong>

                <span>
                  {doc.chunks} passages indexed
                </span>
              </div>

              <button
                className="icon-btn remove-btn"
                title="Remove document"
                aria-label={`Remove ${doc.filename}`}
                onClick={() => remove(doc)}
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}

          {docs.length === 0 && (
            <div className="empty-files">
              Your uploaded documents will appear here.
            </div>
          )}
        </div>

        {/* Sidebar footer */}
        <div className="sidebar-footer">
          <div className="safe">
            <ShieldCheck size={17} />

            <span>
              Local development workspace
            </span>
          </div>

          <span className="caption-small">
            Portfolio prototype · Not multi-user ready
          </span>
        </div>
      </aside>

      {/* MAIN AREA */}
      <main className="main">

        {/* Top navigation */}
        <header className="topbar">
          <button
            className="mobile-menu"
            onClick={() => setShowMobile(true)}
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>

          <div className="breadcrumb">
            Workspace

            <ChevronRight size={14} />

            <strong>
              Knowledge assistant
            </strong>
          </div>

          <div className="top-right">
            <span
              className={`status-dot ${
                health ? "online" : ""
              }`}
            />

            <span>
              {health
                ? "API connected"
                : "Connecting…"}
            </span>

            <div className="avatar">
              S
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="main-body">

          {/* Error banner */}
          {error && (
            <div className="error-banner">
              <CircleHelp size={17} />

              <span>{error}</span>

              <button
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Welcome screen */}
          {messages.length === 0 ? (
            <div className="intro">

              <div className="intro-icon">
                <Sparkles size={29} />
              </div>

              <div className="eyebrow">
                YOUR DOCUMENTS, MADE SEARCHABLE
              </div>

              <h1>
                Answers, backed by
                <br />
                <em>your knowledge.</em>
              </h1>

              <p>
                Upload a document, ask a question,
                and explore the exact source passages
                behind each response.
              </p>

              {/* Feature cards */}
              <div className="feature-cards">
                <div>
                  <Search size={19} />

                  <strong>
                    Smart retrieval
                  </strong>

                  <span>
                    Find information across documents
                  </span>
                </div>

                <div>
                  <BookOpen size={19} />

                  <strong>
                    Source references
                  </strong>

                  <span>
                    See the passages used in each result
                  </span>
                </div>

                <div>
                  <Database size={19} />

                  <strong>
                    Your knowledge base
                  </strong>

                  <span>
                    Manage indexed files in one place
                  </span>
                </div>
              </div>

              {/* Example questions */}
              {docs.length > 0 ? (
                <div className="sample-questions">

                  <div className="sample-title">
                    TRY ASKING <span>↘</span>
                  </div>

                  {examples.map((example) => (
                    <button
                      key={example}
                      onClick={() => ask(example)}
                    >
                      {example}

                      <ChevronRight size={16} />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="start-hint">
                  <Plus size={18} />

                  Start by uploading{" "}
                  <strong>
                    sample_docs/example_company_handbook.txt
                  </strong>
                </div>
              )}
            </div>
          ) : (

            /* CHAT CONVERSATION */
            <div className="conversation">

              <div className="thread-label">
                <Sparkles size={17} />

                KNOWLEDGE ASSISTANT

                <span>·</span>

                {
                  messages.filter(
                    (m) => m.role === "user"
                  ).length
                }{" "}
                questions
              </div>

              {/* Chat messages */}
              {messages.map((m, i) => (
                <div
                  className={`message ${m.role}`}
                  key={i}
                >
                  {m.role === "assistant" && (
                    <div className="message-avatar">
                      <Sparkles size={17} />
                    </div>
                  )}

                  <div className="message-body">

                    {m.role === "user" ? (
                      <div className="user-bubble">
                        {m.content}
                      </div>
                    ) : (
                      <>
                        <div className="assistant-text">
                          {m.answer}
                        </div>

                        {/* Source references */}
                        {m.sources?.length > 0 && (
                          <>
                            <div className="source-list-title">
                              <BookOpen size={15} />

                              Source passages

                              <span>
                                {m.sources.length}
                              </span>
                            </div>

                            <div className="source-grid">
                              {m.sources.map((source) => (
                                <SourceCard
                                  key={source.id}
                                  source={source}
                                />
                              ))}
                            </div>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading indicator */}
              {busy && (
                <div className="loading">
                  <div className="message-avatar">
                    <Sparkles size={17} />
                  </div>

                  <span className="loader" />

                  Searching your knowledge base…
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* CHAT COMPOSER */}
        <div className="composer-wrapper">
          <div className="composer-area">

            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                ask();
              }}
            >
              <input
                value={question}
                onChange={(e) =>
                  setQuestion(e.target.value)
                }
                placeholder={
                  docs.length
                    ? "Ask anything about your documents…"
                    : "Upload a document to start asking questions…"
                }
                disabled={busy || docs.length === 0}
                aria-label="Ask a question"
              />

              <button
                type="submit"
                disabled={
                  !question.trim() ||
                  busy ||
                  docs.length === 0
                }
                aria-label="Send message"
              >
                <SendHorizontal size={18} />
              </button>
            </form>

            <div className="composer-caption">
              <span>
                {health?.mode || "Checking connection"}
              </span>

              <span>
                Answers may be imperfect.
                Verify important details in source files.
              </span>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
