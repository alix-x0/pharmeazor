import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  GraduationCap,
  Send,
  RotateCcw,
  Sparkles,
  User,
  Bot,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const MEDSAFE_BASE = 'http://127.0.0.1:8001';

const SUGGESTED_TOPICS = [
  "Explain the mechanism of action of metformin.",
  "What are the key counselling points for warfarin?",
  "Describe the pharmacokinetics of amoxicillin.",
  "What are the contraindications of NSAIDs?",
  "How do ACE inhibitors differ from ARBs?",
  "Quiz me on drug-drug interactions.",
];

export default function PharmaTutor() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return;

    const userMessage = { role: 'user', content: text.trim() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${MEDSAFE_BASE}/api/v1/conversation/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId,
          user_role: 'pharmacist',
          max_tokens: 512,
          temperature: 0.4,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: "I'm temporarily unavailable. The AI model might still be loading — please try again in a moment." },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleNewSession = () => {
    setMessages([]);
    setSessionId(null);
    setInput('');
    inputRef.current?.focus();
  };

  return (
    <motion.div
      className="flex flex-col h-[calc(100vh-8rem)] w-full pt-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-zinc-100 dark:border-zinc-800 pb-6 px-1">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 flex items-center gap-2">
            <GraduationCap className="w-6 h-6 text-primary" />
            PharmaTutor
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            AI-powered clinical training assistant — ask questions, get quizzed, explore pharmacology.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={handleNewSession}
          className="gap-2 h-9 px-4 rounded-xl text-xs font-semibold"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          New Session
        </Button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto py-6 px-1 space-y-4">
        {messages.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mb-6">
              <Sparkles className="w-8 h-8 text-primary" />
            </div>
            <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight mb-2">
              Start a Training Session
            </h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md mb-8">
              Ask me about drug mechanisms, pharmacokinetics, interactions, counselling points — or pick a topic below.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
              {SUGGESTED_TOPICS.map((topic, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(topic)}
                  className="text-left text-[13px] font-medium text-zinc-600 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-700/50 rounded-xl px-4 py-3 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-200 dark:hover:border-zinc-600 transition-all active:scale-[0.98]"
                >
                  {topic}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Messages */
          messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-white rounded-br-md'
                    : 'bg-zinc-50 dark:bg-zinc-800/50 text-zinc-800 dark:text-zinc-200 border border-zinc-100 dark:border-zinc-700/50 rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-zinc-900 dark:bg-zinc-700 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-white" />
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div className="bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-700/50 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
              <span className="text-[13px] text-zinc-500 dark:text-zinc-400">Thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="border-t border-zinc-100 dark:border-zinc-800 pt-4 pb-2 px-1">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a clinical question..."
            disabled={loading}
            className="flex-1 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-xl px-4 py-3 text-[13.5px] text-zinc-900 dark:text-white placeholder:text-zinc-400 outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/10 transition-all disabled:opacity-50"
          />
          <Button
            type="submit"
            disabled={!input.trim() || loading}
            className="h-[46px] w-[46px] rounded-xl shrink-0 p-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-2 text-center font-medium">
          PharmaTutor is an educational tool. Responses do not replace clinical judgement or prescriber authority.
        </p>
      </div>
    </motion.div>
  );
}
