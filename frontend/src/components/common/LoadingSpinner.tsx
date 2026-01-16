interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
}

/**
 * Loading spinner component with optional message
 */
export function LoadingSpinner({
  size = 'medium',
  message = 'Loading...',
}: LoadingSpinnerProps) {
  const sizeClasses = {
    small: 'spinner-small',
    medium: 'spinner-medium',
    large: 'spinner-large',
  };

  return (
    <div className={`loading-spinner-container ${sizeClasses[size]}`}>
      <div className="loading-spinner" role="status" aria-label="Loading">
        <svg
          className="spinner-svg"
          viewBox="0 0 50 50"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            className="spinner-circle"
            cx="25"
            cy="25"
            r="20"
            fill="none"
            strokeWidth="4"
          />
        </svg>
      </div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
}

export default LoadingSpinner;
