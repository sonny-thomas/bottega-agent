// import React, { useState, useEffect, useRef } from 'react';
// import { Send, Loader } from 'lucide-react';
// import ReactMarkdown from 'react-markdown';
// import './ChatBot.css';

// const TypingIndicator = () => (
//   <div className="typing-indicator">
//     <span className="gradient-text">Bottega-Bot is thinking...</span>
//   </div>
// );

// const ChatMessage = ({ message, isUser }) => {
//   return (
//     <div className={`chat-message ${isUser ? 'user-message' : 'bot-message'}`}>
//       <div className="message-content unicode-text">
//         {isUser ? (
//           <p>{message}</p>
//         ) : (
//           <ReactMarkdown>{message}</ReactMarkdown>
//         )}
//       </div>
//     </div>
//   );
// };

// const BytesThemedChatbot = () => {
//   const [messages, setMessages] = useState([]);
//   const [input, setInput] = useState('');
//   const [threadId, setThreadId] = useState(null);
//   const [isTyping, setIsTyping] = useState(false);
//   const [isBotResponding, setIsBotResponding] = useState(false);
//   const messagesEndRef = useRef(null);

//   useEffect(() => {
//     setThreadId(generateThreadId());
//   }, []);

//   const generateThreadId = () => {
//     return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
//       var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
//       return v.toString(16);
//     });
//   };

//   const scrollToBottom = () => {
//     messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
//   };

//   useEffect(scrollToBottom, [messages]);

//   const cleanBotMessage = (message) => {
//     let cleanedMessage = message.replace(/\u001b\[[0-9;]*m/g, '');
//     cleanedMessage = cleanedMessage.replace(/^==================================\s*Ai Message\s*==================================\s*/, '');
  
//     if (cleanedMessage.trim().startsWith('[{')) {
//       try {
//         const jsonMessage = JSON.parse(cleanedMessage);
//         cleanedMessage = jsonMessage[0].text;
//       } catch (error) {
//         console.error('Error parsing JSON:', error);
//       }
//     }
  
//     cleanedMessage = cleanedMessage.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
//     cleanedMessage = cleanedMessage.replace(/^==================================\s*/, '');
  
//     console.log('Original message:', message);
//     console.log('Cleaned message:', cleanedMessage);
//     return cleanedMessage;
//   };
  
//   const handleSubmit = async (e) => {
//     e.preventDefault();
//     if (!input.trim() || isBotResponding) return;

//     setMessages(prev => [...prev, { text: input, isUser: true }]);
//     setInput('');
//     setIsTyping(true);
//     setIsBotResponding(true);

//     try {
//       const response = await fetch('/chat', {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({ message: input, thread_id: threadId }),
//       });

//       const data = await response.json();
//       console.log('Received data:', data);
      
//       if (data.thread_id) setThreadId(data.thread_id);
      
//       if (data.messages) {
//         const cleanedMessage = cleanBotMessage(data.messages);
//         setMessages(prev => [...prev, { text: cleanedMessage, isUser: false }]);
//       }

//     } catch (error) {
//       console.error('Error:', error);
//     } finally {
//       setIsTyping(false);
//       setIsBotResponding(false);
//     }
//   };
  
//   return (
//     <div className="flex flex-col h-screen bg-gray-100 font-sans">
//       <div className="bg-white p-4 text-center">
//         <h2 className="text-2xl font-bold gradient-text">
//           Bottega Bot <span role="img" aria-label="robot">🤖</span> Bottega Restaurant AI
//         </h2>
//         <p className="gradient-text text-sm mt-1">powered by Zorro AI</p>
//       </div>
//       <div className="gradient-separator"></div>
//       <div className="flex-grow overflow-auto p-4" id="chat-container">
//         {messages.map((msg, index) => (
//           <ChatMessage key={index} message={msg.text} isUser={msg.isUser} />
//         ))}
//         {isTyping && <TypingIndicator />}
//         <div ref={messagesEndRef} />
//       </div>
//       <form onSubmit={handleSubmit} className="p-4 bg-white">
//         <div className="flex">
//           <input
//             type="text"
//             placeholder="Type your message..."
//             value={input}
//             onChange={(e) => setInput(e.target.value)}
//             className="chat-input flex-grow mr-2 p-2"
//             disabled={isBotResponding}
//           />
//           <button 
//             type="submit" 
//             className={`send-button ${isBotResponding ? 'disabled' : ''}`}
//             disabled={isBotResponding}
//           >
//             {isBotResponding ? <Loader size={24} className="animate-spin" /> : <Send size={24} />}
//           </button>
//         </div>
//       </form>
//     </div>
//   );
// };

// export default BytesThemedChatbot;

import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatBot.css';

const TypingIndicator = () => (
  <div className="typing-indicator">
    <span className="gradient-text">Bottega-Bot is thinking...</span>
  </div>
);

const ChatMessage = ({ message, isUser }) => {
  return (
    <div className={`chat-message ${isUser ? 'user-message' : 'bot-message'}`}>
      <div className="message-content unicode-text">
        {isUser ? (
          <p>{message}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message}</ReactMarkdown>
        )}
      </div>
    </div>
  );
};

const BytesThemedChatbot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [threadId, setThreadId] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [isBotResponding, setIsBotResponding] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    setThreadId(generateThreadId());
  }, []);

  const generateThreadId = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const cleanBotMessage = (message) => {
    let cleanedMessage = message.replace(/\u001b\[[0-9;]*m/g, '');
    cleanedMessage = cleanedMessage.replace(/^==================================\s*Ai Message\s*==================================\s*/, '');
  
    if (cleanedMessage.trim().startsWith('[{')) {
      try {
        const jsonMessage = JSON.parse(cleanedMessage);
        cleanedMessage = jsonMessage[0].text;
      } catch (error) {
        console.error('Error parsing JSON:', error);
      }
    }
  
    cleanedMessage = cleanedMessage.trim();
    cleanedMessage = cleanedMessage.replace(/^==================================\s*/, '');
  
    console.log('Original message:', message);
    console.log('Cleaned message:', cleanedMessage);
    return cleanedMessage;
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isBotResponding) return;

    setMessages(prev => [...prev, { text: input, isUser: true }]);
    setInput('');
    setIsTyping(true);
    setIsBotResponding(true);

    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: input, thread_id: threadId }),
      });

      const data = await response.json();
      console.log('Received data:', data);
      
      if (data.thread_id) setThreadId(data.thread_id);
      
      if (data.messages) {
        const cleanedMessage = cleanBotMessage(data.messages);
        setMessages(prev => [...prev, { text: cleanedMessage, isUser: false }]);
      }

    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsTyping(false);
      setIsBotResponding(false);
    }
  };
  
  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans">
      <div className="bg-white p-4 text-center">
        <h2 className="text-2xl font-bold gradient-text">
          Bottega Bot <span role="img" aria-label="robot">🤖</span> Bottega Restaurant AI
        </h2>
        <p className="gradient-text text-sm mt-1">created by Kabeer Thockchom</p>
      </div>
      <div className="gradient-separator"></div>
      <div className="flex-grow overflow-auto p-4" id="chat-container">
        {messages.map((msg, index) => (
          <ChatMessage key={index} message={msg.text} isUser={msg.isUser} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="p-4 bg-white">
        <div className="flex">
          <input
            type="text"
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="chat-input flex-grow mr-2 p-2"
            disabled={isBotResponding}
          />
          <button 
            type="submit" 
            className={`send-button ${isBotResponding ? 'disabled' : ''}`}
            disabled={isBotResponding}
          >
            {isBotResponding ? <Loader size={24} className="animate-spin" /> : <Send size={24} />}
          </button>
        </div>
      </form>
    </div>
  );
};

export default BytesThemedChatbot;