import { useState, useEffect, useRef, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import clsx from 'clsx';

export interface MenuItem {
  id: string;
  label: string;
  icon?: ReactNode;
  shortcut?: string;
  disabled?: boolean;
  separator?: boolean;
  danger?: boolean;
  onClick?: () => void;
}

export interface ContextMenuProps {
  items: MenuItem[];
  position: { x: number; y: number } | null;
  onClose: () => void;
}

/**
 * Context Menu Component
 * 
 * カスタムコンテキストメニュー
 * 右クリックで表示されるポップアップメニュー
 */
export function ContextMenu({ items, position, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Adjust position to keep menu in viewport
  const [adjustedPosition, setAdjustedPosition] = useState(position);

  useEffect(() => {
    if (position && menuRef.current) {
      const menu = menuRef.current;
      const rect = menu.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let x = position.x;
      let y = position.y;

      // Adjust if menu goes off right edge
      if (x + rect.width > viewportWidth) {
        x = viewportWidth - rect.width - 8;
      }

      // Adjust if menu goes off bottom edge
      if (y + rect.height > viewportHeight) {
        y = viewportHeight - rect.height - 8;
      }

      // Ensure minimum position
      x = Math.max(8, x);
      y = Math.max(8, y);

      setAdjustedPosition({ x, y });
    }
  }, [position]);

  if (!position) return null;

  return createPortal(
    <div
      ref={menuRef}
      className={clsx(
        'fixed z-50 min-w-[180px] max-w-[280px]',
        'bg-dc-dark-800 border border-dc-dark-700 rounded-lg shadow-xl',
        'py-1 overflow-hidden',
        'animate-in fade-in zoom-in-95 duration-100'
      )}
      style={{
        left: adjustedPosition?.x ?? position.x,
        top: adjustedPosition?.y ?? position.y,
      }}
    >
      {items.map((item, index) => {
        if (item.separator) {
          return (
            <div
              key={`separator-${index}`}
              className="h-px bg-dc-dark-700 my-1"
            />
          );
        }

        return (
          <button
            key={item.id}
            onClick={() => {
              if (!item.disabled) {
                item.onClick?.();
                onClose();
              }
            }}
            disabled={item.disabled}
            className={clsx(
              'w-full px-3 py-1.5 text-left flex items-center gap-3',
              'text-sm transition-colors',
              item.disabled
                ? 'text-dc-dark-500 cursor-not-allowed'
                : item.danger
                ? 'text-dc-accent-danger hover:bg-dc-accent-danger/10'
                : 'text-dc-dark-200 hover:bg-dc-dark-700 hover:text-white'
            )}
          >
            {item.icon && (
              <span className="w-4 h-4 flex items-center justify-center">
                {item.icon}
              </span>
            )}
            <span className="flex-1">{item.label}</span>
            {item.shortcut && (
              <span className="text-xs text-dc-dark-500 ml-4">
                {item.shortcut}
              </span>
            )}
          </button>
        );
      })}
    </div>,
    document.body
  );
}

/**
 * Hook for using context menu
 */
export function useContextMenu<T = unknown>() {
  const [menuState, setMenuState] = useState<{
    position: { x: number; y: number } | null;
    data: T | null;
  }>({
    position: null,
    data: null,
  });

  const openMenu = (e: React.MouseEvent, data?: T) => {
    e.preventDefault();
    e.stopPropagation();
    setMenuState({
      position: { x: e.clientX, y: e.clientY },
      data: data ?? null,
    });
  };

  const closeMenu = () => {
    setMenuState({ position: null, data: null });
  };

  return {
    position: menuState.position,
    data: menuState.data,
    openMenu,
    closeMenu,
    isOpen: menuState.position !== null,
  };
}

export default ContextMenu;
