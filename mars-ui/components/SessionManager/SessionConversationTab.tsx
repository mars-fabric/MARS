"use client";

import { User, Bot, MessageSquare } from "lucide-react";
import { ConversationMessage } from "@/types/sessions";

interface SessionConversationTabProps {
  messages: ConversationMessage[];
}

export function SessionConversationTab({ messages }: SessionConversationTabProps) {
  if (!messages || messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <MessageSquare className="w-10 h-10 mx-auto mb-3 text-gray-500" />
          <p className="text-sm">No conversation history</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3 bg-gray-900">
      {messages.map((msg, idx) => {
        const isUser = msg.role === "user";
        return (
          <div
            key={idx}
            className={`flex ${isUser ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg p-3 ${
                isUser
                  ? "bg-blue-600/20 border border-blue-500/30"
                  : "bg-gray-800 border border-gray-700"
              }`}
            >
              {/* Header */}
              <div className="flex items-center gap-2 mb-1">
                {isUser ? (
                  <User className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                )}
                <span
                  className={`text-xs font-medium ${
                    isUser ? "text-blue-400" : "text-purple-400"
                  }`}
                >
                  {isUser ? "User" : msg.agent || "Assistant"}
                </span>
                {msg.timestamp && (
                  <span className="text-xs text-gray-500 ml-auto">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>

              {/* Content */}
              <p className="text-sm text-gray-300 whitespace-pre-wrap break-words">
                {msg.content}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
