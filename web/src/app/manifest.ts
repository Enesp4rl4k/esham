import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Esham — BIST & Piyasa İstihbarat Platformu",
    short_name: "Esham",
    description:
      "Borsa İstanbul, VİOP, KAP bildirimleri, TÜRİB emtia ve makroekonomik veriler için finansal istihbarat platformu.",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0a",
    theme_color: "#f59e0b",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
