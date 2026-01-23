import { useEffect, useRef, useCallback } from 'react';
import { useStore } from '../store';

/**
 * Custom hook for WebSocket connection management
 * Handles automatic reconnection and connection state
 */
export function useWebSocket() {
  const { connect, disconnect, isConnected, connectionError } = useStore();
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  useEffect(() => {
    // Connect on mount
    connect();

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Auto-reconnect logic
  useEffect(() => {
    if (!isConnected && connectionError && reconnectAttempts.current < maxReconnectAttempts) {
      const timeout = setTimeout(() => {
        reconnectAttempts.current += 1;
        connect();
      }, Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)); // Exponential backoff

      return () => clearTimeout(timeout);
    }

    // Reset attempts on successful connection
    if (isConnected) {
      reconnectAttempts.current = 0;
    }
    
    return undefined;
  }, [isConnected, connectionError, connect]);

  return { isConnected, connectionError, reconnectAttempts: reconnectAttempts.current };
}

/**
 * Custom hook for auto-scrolling to bottom of a container
 */
export function useAutoScroll<T extends HTMLElement>(
  dependency: unknown,
  enabled: boolean = true
) {
  const ref = useRef<T>(null);

  useEffect(() => {
    if (enabled && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [dependency, enabled]);

  return ref;
}

/**
 * Custom hook for keyboard shortcuts
 */
export function useKeyboardShortcut(
  key: string,
  callback: () => void,
  modifiers: { ctrl?: boolean; shift?: boolean; alt?: boolean; meta?: boolean } = {}
) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const { ctrl = false, shift = false, alt = false, meta = false } = modifiers;

      if (
        event.key.toLowerCase() === key.toLowerCase() &&
        event.ctrlKey === ctrl &&
        event.shiftKey === shift &&
        event.altKey === alt &&
        event.metaKey === meta
      ) {
        event.preventDefault();
        callbackRef.current();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [key, modifiers]);
}

/**
 * Custom hook for debounced values
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

// Need to import useState for useDebounce
import { useState } from 'react';

/**
 * Custom hook for detecting clicks outside a ref
 */
export function useClickOutside<T extends HTMLElement>(
  callback: () => void
): React.RefObject<T> {
  const ref = useRef<T>(null);
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        callbackRef.current();
      }
    };

    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return ref;
}

/**
 * Custom hook for local storage with JSON serialization
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const valueToStore = value instanceof Function ? value(storedValue) : value;
        setStoredValue(valueToStore);
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      } catch (error) {
        console.error(`Error saving to localStorage: ${error}`);
      }
    },
    [key, storedValue]
  );

  return [storedValue, setValue];
}

/**
 * Custom hook for window resize events
 */
export function useWindowSize() {
  const [size, setSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  useEffect(() => {
    const handler = () => {
      setSize({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  return size;
}

/**
 * Custom hook for interval with cleanup
 */
export function useInterval(callback: () => void, delay: number | null) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (delay === null) return;

    const id = setInterval(() => callbackRef.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

/**
 * Custom hook for copy to clipboard
 */
export function useCopyToClipboard(): [boolean, (text: string) => Promise<void>] {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      setCopied(false);
    }
  }, []);

  return [copied, copy];
}
