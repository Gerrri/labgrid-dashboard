import type { CommandOutput, ExecutionTransport } from "../../types";

interface OutputViewerProps {
  outputs: CommandOutput[];
  maxHeight?: string;
  onClear?: () => void;
}

/**
 * Terminal-like output viewer for command results
 */
export function OutputViewer({
  outputs,
  maxHeight = "300px",
  onClear,
}: OutputViewerProps) {
  if (outputs.length === 0) {
    return (
      <div className="output-viewer empty">
        <p className="no-output">
          No command output yet. Execute a command to see results.
        </p>
      </div>
    );
  }

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const getTransportLabel = (output: CommandOutput): ExecutionTransport | null =>
    output.execution_transport ?? null;

  return (
    <div className="output-viewer" style={{ maxHeight }}>
      {outputs.map((output, index) => {
        const transport = getTransportLabel(output);
        const showClearButton = index === 0 && onClear !== undefined;

        return (
          <div
            key={`${output.command}-${output.timestamp}-${output.exit_code}-${index}`}
            className="output-entry"
          >
            <div className="output-header">
              <code className="output-command">$ {output.command}</code>
              <div className="output-meta">
                {transport && (
                  <span
                    className="transport-label"
                    title="Transport used for this execution"
                  >
                    {transport}
                  </span>
                )}
                <span
                  className={`exit-code ${output.exit_code === 0 ? "success" : "error"}`}
                  title={output.exit_code === 0 ? "Success" : "Error"}
                >
                  {output.exit_code === 0 ? "✓" : "✗"} {output.exit_code}
                </span>
                {showClearButton && (
                  <button
                    className="btn-clear btn-clear-terminal"
                    onClick={onClear}
                    title="Clear output"
                  >
                    Clear
                  </button>
                )}
                <span className="timestamp" title={output.timestamp}>
                  {formatTimestamp(output.timestamp)}
                </span>
              </div>
            </div>
            <pre className="output-content">{output.output}</pre>
          </div>
        );
      })}
    </div>
  );
}

export default OutputViewer;
