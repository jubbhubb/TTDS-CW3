import { Search } from "lucide-react";
import { useState } from "react";
import { Switch } from "./ui/switch";

interface LandingSearchProps {
  onSearch: (query: string, language: 'en' | 'es') => void;
}

export function LandingSearch({ onSearch }: LandingSearchProps) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<'en' | 'es'>('en');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query, language);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center p-8">
      <div className="max-w-3xl w-full">
        <div className="text-center mb-12">
          <h1 className="text-6xl font-bold mb-4 bg-gradient-to-r from-green-500 to-emerald-600 bg-clip-text text-transparent">
            Lyric Search
          </h1>
          <p className="text-xl text-gray-600">
            Search for songs by title, artist, or lyrics
          </p>
        </div>

        <form onSubmit={handleSubmit} className="relative">
          <div className="relative flex items-center">
            <Search className="absolute left-6 size-6 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for a song or lyrics..."
              className="w-full pl-16 pr-6 py-6 text-lg border-2 border-gray-200 rounded-full shadow-lg focus:outline-none focus:border-blue-500 focus:shadow-xl transition-all"
              autoFocus
            />
          </div>
          <button
            type="submit"
            className="absolute right-2 top-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white px-8 py-4 rounded-full font-semibold hover:from-green-600 hover:to-emerald-700 transition-all"
          >
            Search
          </button>

          <div className="mt-4 flex justify-center items-center gap-3 text-sm font-medium text-gray-700">
            <span className={language === 'en' ? 'text-gray-900' : 'text-gray-500'}>English</span>
            <Switch
              checked={language === 'es'}
              onCheckedChange={(checked) => setLanguage(checked ? 'es' : 'en')}
              className="data-[state=unchecked]:bg-gray-500 data-[state=checked]:bg-green-600 [&_[data-slot=switch-thumb]]:bg-white"
              aria-label="Toggle search language between English and Spanish"
            />
            <span className={language === 'es' ? 'text-gray-900' : 'text-gray-500'}>Spanish</span>
          </div>
        </form>
      </div>
    </div>
  );
}