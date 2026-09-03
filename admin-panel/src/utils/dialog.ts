import { useEffect } from 'react';

/**
 * Стек открытых диалогов: модалка может открываться поверх drawer'а.
 * Стек нужен для двух вещей:
 *  1) прокрутка body возвращается только когда закрыт последний диалог;
 *  2) Escape закрывает только верхний диалог, а не все сразу.
 */
const stack: symbol[] = [];
let previousOverflow = '';
let previousPaddingRight = '';

const lockScroll = () => {
  const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
  previousOverflow = document.body.style.overflow;
  previousPaddingRight = document.body.style.paddingRight;
  document.body.style.overflow = 'hidden';
  if (scrollbarWidth > 0) {
    document.body.style.paddingRight = `${scrollbarWidth}px`;
  }
};

const unlockScroll = () => {
  document.body.style.overflow = previousOverflow;
  document.body.style.paddingRight = previousPaddingRight;
};

/** Блокирует прокрутку страницы и закрывает верхний диалог по Escape. */
export function useDialogBehavior(isOpen: boolean, onClose: () => void) {
  useEffect(() => {
    if (!isOpen) return;

    const id = Symbol('dialog');
    if (stack.length === 0) lockScroll();
    stack.push(id);

    const handleKeyDown = (e: KeyboardEvent) => {
      // Реагирует только верхний диалог в стеке.
      if (e.key === 'Escape' && stack[stack.length - 1] === id) {
        e.stopPropagation();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      const index = stack.lastIndexOf(id);
      if (index !== -1) stack.splice(index, 1);
      if (stack.length === 0) unlockScroll();
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);
}
