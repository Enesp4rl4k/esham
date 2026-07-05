import { Mail } from "lucide-react";

export function Newsletter() {
  return (
    <section className="py-24 bg-gradient-to-b from-zinc-950 to-black border-t border-zinc-900">
      <div className="container mx-auto px-6 max-w-4xl text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-950 text-cyan-400 mb-6">
          <Mail className="w-8 h-8" />
        </div>
        <h2 className="text-3xl md:text-5xl font-outfit font-bold mb-4">
          Piyasalar Her Sabah Kutunuzda
        </h2>
        <p className="text-zinc-400 text-lg mb-8 max-w-2xl mx-auto font-light">
          BIST bülteni, makro özetler ve yeni halka arz analizlerini kaçırmamak için email bültenimize ücretsiz katılın.
        </p>
        
        {/* FORMSPREE INTEGRATION */}
        <form 
          action="https://formspree.io/f/xnjkwdkr" 
          method="POST"
          className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto"
        >
          <input
            type="email"
            name="email"
            placeholder="ornek@sirket.com"
            required
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-full px-6 py-4 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
          <button
            type="submit"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-full px-8 py-4 transition-colors whitespace-nowrap"
          >
            Abone Ol
          </button>
        </form>
        <p className="text-zinc-600 text-sm mt-4">
          İstediğiniz zaman tek tıkla abonelikten çıkabilirsiniz. Spam yok.
        </p>
      </div>
    </section>
  );
}
