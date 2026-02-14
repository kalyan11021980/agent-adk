export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-teal-400"
          style={{
            animation: "bounce 1.4s infinite ease-in-out",
            animationDelay: `${i * 0.16}s`,
          }}
        />
      ))}
      <style jsx>{`
        @keyframes bounce {
          0%,
          80%,
          100% {
            transform: scale(0.6);
            opacity: 0.4;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
