import { useState, useRef, useEffect } from "react";
import { Sparkles, X, Send, Trash2, ChevronDown } from "lucide-react";
import { askAIQuery } from "@/services/apiService";

function MessageBubble({ message }) {
  const isUser = message.role === "user";

  // Simple renderer: split on newlines and bold **text**
  const renderText = (text) => {
    return text.split("\n").map((line, i) => {
      // Bold: **text**
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      return (
        <p key={i} className={i > 0 ? "mt-1" : ""}>
          {parts.map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? (
              <strong key={j}>{part.slice(2, -2)}</strong>
            ) : (
              part
            )
          )}
        </p>
      );
    });
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-violet-500 flex items-center justify-center mr-2 mt-0.5 shrink-0">
          <Sparkles size={12} className="text-white" />
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-violet-500 text-white rounded-tr-sm"
            : "bg-gray-100 text-gray-800 rounded-tl-sm"
        }`}
      >
        {renderText(message.content)}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-1 text-xs opacity-60">
            Used: {message.toolCalls.map((t) => t.replace(/_/g, " ")).join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3">
      <div className="w-6 h-6 rounded-full bg-violet-500 flex items-center justify-center mr-2 mt-0.5 shrink-0">
        <Sparkles size={12} className="text-white" />
      </div>
      <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-3 py-2">
        <div className="flex gap-1 items-center h-4">
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

const WELCOME_MESSAGE = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm your Jewel India ERP assistant. Ask me anything about your business data — sales, purchases, stock, ledger balances, gold rates, and more.",
};

export default function AIAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { id: Date.now(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await askAIQuery(text);
      if (result.success) {
        const aiMsg = {
          id: Date.now() + 1,
          role: "assistant",
          content: result.data.response,
          toolCalls: result.data.tool_calls || [],
        };
        setMessages((prev) => [...prev, aiMsg]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            content: `Sorry, I encountered an error: ${result.error || "Unknown error"}`,
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "Sorry, I couldn't connect to the AI service. Please check your internet connection.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([WELCOME_MESSAGE]);
  };

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-violet-500 hover:bg-violet-600 text-white shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95"
        title="AI Assistant"
      >
        {isOpen ? <ChevronDown size={20} /> : <Sparkles size={20} />}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-22 right-6 z-50 w-96 h-[480px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-violet-500 text-white">
            <div className="flex items-center gap-2">
              <Sparkles size={16} />
              <span className="font-semibold text-sm">AI Assistant</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={clearChat}
                className="p-1 rounded hover:bg-violet-600 transition-colors"
                title="Clear chat"
              >
                <Trash2 size={14} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded hover:bg-violet-600 transition-colors"
                title="Close"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="px-3 pb-3 pt-2 border-t border-gray-100">
            <div className="flex items-end gap-2 bg-gray-50 rounded-xl px-3 py-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about sales, stock, ledgers..."
                rows={1}
                className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none outline-none max-h-24"
                style={{ lineHeight: "1.5" }}
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                className="w-8 h-8 rounded-lg bg-violet-500 hover:bg-violet-600 disabled:bg-gray-300 text-white flex items-center justify-center transition-colors shrink-0"
              >
                <Send size={14} />
              </button>
            </div>
            <p className="text-[10px] text-gray-400 text-center mt-1">
              Press Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>
      )}
    </>
  );
}
