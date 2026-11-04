import {useState} from 'react';
import type {ReactNode} from 'react';

/** Disclosure only: the existing import form remains mounted while closed. */
export function RecordImportDisclosure({initiallyOpen, children}: {initiallyOpen: boolean; children: ReactNode}) {
  const [open, setOpen] = useState(initiallyOpen);
  return <details className="record-import-disclosure" data-testid="record-import-disclosure"
    open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Add an original record</summary>
    <p className="muted small">Select, inspect and explicitly import a fictional text file. Opening or closing this form does not upload or discard your selection.</p>
    {children}
  </details>;
}
