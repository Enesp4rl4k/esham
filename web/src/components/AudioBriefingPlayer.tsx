"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  RotateCcw,
  Sparkles,
  Radio,
} from "lucide-react";

interface AudioBriefingPlayerProps {
  briefingText?: string;
  title?: string;
}

export function AudioBriefingPlayer({
  briefingText = "Esham Yapay Zeka Piyasa Analizi. Borsa İstanbul 100 endeksi günü yüzde eksi 0 virgül 19 düşüşle 10 bin 941 puandan sürdürüyor. Türk Hava Yolları ve Aselsan alıcılı seyrederken, bankacılık endeksinde kâr satışları izleniyor. Türkiye 5 yıllık CDS primi 254 baz puanda, VİOP vadeli kontratı ise spot piyasaya göre 339 puan primli işlem görüyor.",
  title = "90 Saniyelik Sesli Piyasa Brifingi",
}: AudioBriefingPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [rate, setRate] = useState<number>(1.0);
  const [progress, setProgress] = useState(0);
  const [supported, setSupported] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      setSupported(true);
    }
  }, []);

  const handlePlayToggle = () => {
    if (!supported) return;

    if (isPlaying) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      setProgress(0);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(briefingText);
    utterance.lang = "tr-TR";
    utterance.rate = rate;

    // Türkçe ses bulmaya çalış
    const voices = window.speechSynthesis.getVoices();
    const trVoice = voices.find((v) => v.lang.startsWith("tr"));
    if (trVoice) utterance.voice = trVoice;

    utterance.onboundary = (e) => {
      if (briefingText.length > 0) {
        setProgress(Math.min(100, (e.charIndex / briefingText.length) * 100));
      }
    };

    utterance.onend = () => {
      setIsPlaying(false);
      setProgress(100);
      setTimeout(() => setProgress(0), 1000);
    };

    utterance.onerror = () => {
      setIsPlaying(false);
      setProgress(0);
    };

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
    setIsPlaying(true);
  };

  const handleRateChange = (newRate: number) => {
    setRate(newRate);
    if (isPlaying) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      setTimeout(() => {
        handlePlayToggle();
      }, 100);
    }
  };

  return (
    <div className="rounded-2xl border border-zinc-800 bg-gradient-to-r from-zinc-950 via-zinc-900/90 to-zinc-950 p-4 md:p-5 shadow-2xl backdrop-blur-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Sol Taraf: İkon ve Bilgi */}
        <div className="flex items-center gap-3">
          <button
            onClick={handlePlayToggle}
            className={`p-3 rounded-xl transition-all shadow-lg shrink-0 flex items-center justify-center ${
              isPlaying
                ? "bg-rose-500 text-white shadow-rose-500/20 animate-pulse"
                : "bg-cyan-500 text-zinc-950 hover:bg-cyan-400 shadow-cyan-500/20"
            }`}
            title={isPlaying ? "Durdur" : "Piyasa Brifingini Dinle"}
          >
            {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
          </button>

          <div>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-[11px] font-mono font-bold uppercase tracking-wider text-cyan-400">
                <Radio className="w-3.5 h-3.5 animate-pulse" /> AI Voice Briefing
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                90sn
              </span>
            </div>
            <h4 className="text-sm font-bold text-white tracking-tight mt-0.5">
              {title}
            </h4>
          </div>
        </div>

        {/* Sağ Taraf: Ekolayzır ve Hız Seçici */}
        <div className="flex items-center gap-4 self-end sm:self-auto">
          {/* Görsel Ekolayzır Barları */}
          <div className="flex items-end gap-1 h-5 px-2">
            {[40, 75, 100, 60, 90, 45, 80].map((h, i) => (
              <div
                key={i}
                className={`w-1 rounded-full transition-all duration-150 ${
                  isPlaying ? "bg-cyan-400 animate-pulse" : "bg-zinc-800"
                }`}
                style={{
                  height: isPlaying ? `${Math.max(20, (h * (progress + 20)) % 100)}%` : "20%",
                }}
              />
            ))}
          </div>

          {/* Oynatma Hızı */}
          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 text-[11px] font-mono">
            {[1.0, 1.25, 1.5].map((r) => (
              <button
                key={r}
                onClick={() => handleRateChange(r)}
                className={`px-2 py-0.5 rounded transition-all ${
                  rate === r
                    ? "bg-cyan-500/20 text-cyan-400 font-bold"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {r}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* İlerleme Çubuğu */}
      {isPlaying && (
        <div className="w-full bg-zinc-800 h-1 rounded-full mt-3 overflow-hidden">
          <div
            className="bg-cyan-400 h-full rounded-full transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
