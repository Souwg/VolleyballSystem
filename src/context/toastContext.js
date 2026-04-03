import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
} from "react";
import { setAuthActions } from "../front/js/utils/authFetch";

const ToastContext = createContext();

export const useToast = () => useContext(ToastContext);

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const timeoutRef = useRef(null);

  const showToast = (message, type = "info") => {
    const id = crypto.randomUUID();

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    setToasts([{ id, message, type }]);

    timeoutRef.current = setTimeout(() => {
      setToasts([]);
    }, 3000);
  };

  useEffect(() => {
    setAuthActions(null, showToast);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}

      <div className="app-toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`app-toast ${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
