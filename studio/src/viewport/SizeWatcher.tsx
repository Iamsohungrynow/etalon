import { useThree } from "@react-three/fiber";
import { useEffect } from "react";

interface SizeWatcherProps {
  /** Called with the canvas size each time it changes and is non-zero. */
  onSize: (width: number, height: number) => void;
}

/**
 * Inside a <Canvas frameloop="demand">: the canvas is measured after it is created, so the
 * first frame would be drawn at 0 × 0 and never again. This reports the real size, so the
 * viewport can frame its camera and request a frame once there is something to draw on.
 */
export function SizeWatcher({ onSize }: SizeWatcherProps) {
  const width = useThree((state) => state.size.width);
  const height = useThree((state) => state.size.height);
  useEffect(() => {
    if (width > 0 && height > 0) onSize(width, height);
  }, [width, height, onSize]);
  return null;
}
