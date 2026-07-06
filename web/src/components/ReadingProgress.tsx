"use client";

import { useEffect, useState } from "react";

/**
 * Sayfanın kaydırma ilerlemesini gösteren ince bir çubuk.
 * Sticky header'ın hemen altına yerleştirilmek için z-40 kullanılır.
 * Rapor sayfasına özgüdür; layout'a eklenmez, doğrudan rapor sayfasında render edilir.
 */
export function ReadingProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function onScroll() {
      const scrollTop = window.scrollY;
      const docHeight =
        document.documentElement.scrollHeight -
        document.documentElement.clientHeight;
      const pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      setProgress(Math.min(100, Math.max(0, pct)));
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll(); // ilk render'da hesapla
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Okuma ilerlemesi"
      className="fixed top-16 left-0 right-0 z-40 h-0.5 bg-transparent pointer-events-none"
    >
      <div
        className="h-full bg-cyan-500 transition-[width] duration-75 ease-linear"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
