interface ErrorMessageProps {
  error: string;
  onRetry?: () => void;
  title?: string;
}

/**
 * Error message component with optional retry button
 */
export function ErrorMessage({
  error,
  onRetry,
  title = 'Error',
}: ErrorMessageProps) {
  return (
    <div className="error-message" role="alert">
      <div className="error-content">
        <span className="error-icon" aria-hidden="true">
          ⚠
        </span>
        <div className="error-text">
          <strong className="error-title">{title}</strong>
          <p className="error-description">{error}</p>
        </div>
      </div>
      {onRetry && (
        <button className="btn-retry" onClick={onRetry} type="button">
          Retry
        </button>
      )}
    </div>
  );
}

export default ErrorMessage;
