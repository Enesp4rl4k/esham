/**
 * Ana sayfa düzeni (bölüm sırası + gizlenenler) — saf fonksiyonlar.
 * Kullanıcı tercihi tarayıcıda saklanır; yeni eklenen bölümler eski kayıtlarda kendiliğinden görünür.
 */
export interface HomeLayout {
  order: string[];
  hidden: string[];
}

export const STORAGE_KEY = "esham:home:v1";

/** Bilinmeyen kimlikleri atar, eksik bölümleri varsayılan sırayla sona ekler, tekrarları temizler. */
export function normalize(stored: unknown, allIds: string[], defaults: HomeLayout): HomeLayout {
  const s = stored as Partial<HomeLayout> | null;
  if (!s || !Array.isArray(s.order)) return { order: [...defaults.order], hidden: [...defaults.hidden] };
  const known = new Set(allIds);
  const order: string[] = [];
  for (const id of s.order) if (typeof id === "string" && known.has(id) && !order.includes(id)) order.push(id);
  for (const id of defaults.order) if (known.has(id) && !order.includes(id)) order.push(id);
  const hidden = Array.isArray(s.hidden) ? [...new Set(s.hidden.filter((id): id is string => typeof id === "string" && known.has(id)))] : [];
  return { order, hidden };
}

export function move(layout: HomeLayout, id: string, dir: -1 | 1): HomeLayout {
  const i = layout.order.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= layout.order.length) return layout;
  const order = [...layout.order];
  [order[i], order[j]] = [order[j], order[i]];
  return { ...layout, order };
}

export function toggle(layout: HomeLayout, id: string): HomeLayout {
  const hidden = layout.hidden.includes(id) ? layout.hidden.filter((h) => h !== id) : [...layout.hidden, id];
  return { ...layout, hidden };
}

/** Görünen bölümler, kullanıcının sırasıyla. */
export function visibleOrder(layout: HomeLayout): string[] {
  return layout.order.filter((id) => !layout.hidden.includes(id));
}

export function read(allIds: string[], defaults: HomeLayout): HomeLayout {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return normalize(raw ? JSON.parse(raw) : null, allIds, defaults);
  } catch {
    return { order: [...defaults.order], hidden: [...defaults.hidden] };
  }
}

export function write(layout: HomeLayout): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    /* gizli pencere / dolu depolama: tercih yalnızca bu oturumda geçerli */
  }
}

export function clear(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* yoksay */
  }
}

/**
 * İlk boyamadan önce çalışan satır içi betik: kayıtlı düzeni geçici bir <style> ile (CSS `order`/`display`)
 * uygular, böylece sayfa varsayılan sıradan kayıtlı sıraya "zıplamaz". Hidrasyondan sonra bileşen
 * <style id="home-pre">'yi kaldırıp düzeni DOM sırasıyla (erişilebilir) uygular.
 */
export const PRE_PAINT_SCRIPT = `(function(){try{var l=JSON.parse(localStorage.getItem(${JSON.stringify(STORAGE_KEY)}));if(!l||!Array.isArray(l.order))return;var ok=/^[a-z0-9-]+$/,c='';l.order.forEach(function(id,i){if(typeof id==='string'&&ok.test(id))c+='[data-home-section="'+id+'"]{order:'+i+'}'});(Array.isArray(l.hidden)?l.hidden:[]).forEach(function(id){if(typeof id==='string'&&ok.test(id))c+='[data-home-section="'+id+'"]{display:none}'});var s=document.createElement('style');s.id='home-pre';s.textContent=c;document.head.appendChild(s)}catch(e){}})();`;
