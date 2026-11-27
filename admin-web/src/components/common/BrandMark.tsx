import React from 'react';
import symbolUrl from '../../assets/brand/mediconnect-symbol.png';

/**
 * MediConnect brand symbol (R01): heart, ECG waveform, medical cross and orbit from the official logo, without the
 * wordmark, so it can sit beside the existing "MediConnect" title text. The image keeps its proportions
 * (object-contain) and reads on both the white sidebar and the dark login/loading screens.
 * Decorative by default because every placement shows the name as text next to it.
 */
export const BrandMark: React.FC<{ className?: string; label?: string }> = ({ className = 'h-9 w-9', label }) => (
  <img
    src={symbolUrl}
    alt={label ?? ''}
    aria-hidden={label ? undefined : true}
    data-testid="brand-mark"
    draggable={false}
    className={`shrink-0 object-contain select-none ${className}`}
  />
);
