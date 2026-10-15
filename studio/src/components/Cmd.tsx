import type { ReactNode } from "react";

interface CmdProps {
  children?: ReactNode;
}

/** A command or file name inside a translated sentence: `<cmd>etalon studio</cmd>`. */
export function Cmd({ children }: CmdProps) {
  return (
    <code translate="no" className="font-mono text-dense text-text">
      {children}
    </code>
  );
}
