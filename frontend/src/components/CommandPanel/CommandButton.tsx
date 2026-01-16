import type { Command } from '../../types';

interface CommandButtonProps {
  command: Command;
  onExecute: (commandName: string) => void;
  isExecuting: boolean;
  disabled?: boolean;
}

/**
 * Button for executing a single command
 */
export function CommandButton({
  command,
  onExecute,
  isExecuting,
  disabled = false,
}: CommandButtonProps) {
  const handleClick = () => {
    if (!isExecuting && !disabled) {
      onExecute(command.name);
    }
  };

  return (
    <button
      className={`command-button ${isExecuting ? 'executing' : ''}`}
      onClick={handleClick}
      disabled={isExecuting || disabled}
      title={command.description}
    >
      {isExecuting ? (
        <>
          <span className="spinner" aria-hidden="true">⟳</span>
          <span>Running...</span>
        </>
      ) : (
        <>
          <span className="command-icon" aria-hidden="true">▶</span>
          <span>{command.name}</span>
        </>
      )}
    </button>
  );
}

export default CommandButton;
