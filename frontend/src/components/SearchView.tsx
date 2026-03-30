import { SearchFilters } from "./SearchFilters";
import { SearchResult } from "./SearchResult";
import { Search, Home } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Switch } from "./ui/switch";

interface Song {
  id: string;
  title: string;
  author: string;
  snippet: string;
  year?: string;
  language?: string;
  imageUrl?: string;
}

interface SearchViewProps {
  songs: Song[];
  searchQuery: string;
  searchLanguage: 'en' | 'es';
  onSearchChange: (query: string, language: 'en' | 'es') => void;
  onBackToSearch?: () => void;
  onSongSelect: (songId: string) => void;
}

export function SearchView({ songs, searchQuery, searchLanguage, onSearchChange, onBackToSearch, onSongSelect }: SearchViewProps) {
  const languageMap: Record<string, string> = {
    english: 'en',
    spanish: 'es',
    french: 'fr',
    german: 'de',
    italian: 'it',
    portuguese: 'pt',
    japanese: 'ja',
    korean: 'ko',
    other: 'other',
  };
  const knownLanguageCodes = new Set(['en', 'es', 'fr', 'de', 'it', 'pt', 'ja', 'ko']);

  const [query, setQuery] = useState(searchQuery);
  const [language, setLanguage] = useState<'en' | 'es'>(searchLanguage);
  const [fromYear, setFromYear] = useState<string>('');
  const [toYear, setToYear] = useState<string>('');
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([]);

  useEffect(() => {
    setQuery(searchQuery);
  }, [searchQuery]);

  useEffect(() => {
    setLanguage(searchLanguage);
  }, [searchLanguage]);

  const handleYearRangeChange = (from: string, to: string) => {
    setFromYear(from);
    setToYear(to);
  };

  const handleLanguageChange = (language: string) => {
    setSelectedLanguages(prev =>
      prev.includes(language)
        ? prev.filter(l => l !== language)
        : [...prev, language]
    );
  };

  const handleClearAll = () => {
    setFromYear('');
    setToYear('');
    setSelectedLanguages([]);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    onSearchChange(query, language);
  };

  const parseYear = (value: string | undefined): number | undefined => {
    if (value === undefined || value.trim() === '') {
      return undefined;
    }

    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? undefined : parsed;
  };

  const filteredResults = useMemo(() => {
    const minYear = parseYear(fromYear);
    const maxYear = parseYear(toYear);
    const selectedLanguageCodes = selectedLanguages.map((label) => {
      const key = label.trim().toLowerCase();
      return languageMap[key] ?? key;
    });
    const includeOther = selectedLanguageCodes.includes('other');
    const chosenKnownCodes = selectedLanguageCodes.filter((code) => code !== 'other');

    return songs.filter((song) => {
      const songYear = parseYear(song.year);
      if (minYear !== undefined || maxYear !== undefined) {
        if (songYear === undefined) {
          return false;
        }

        if (minYear !== undefined && songYear < minYear) {
          return false;
        }

        if (maxYear !== undefined && songYear > maxYear) {
          return false;
        }
      }

      if (selectedLanguageCodes.length > 0) {
        const songLanguage = song.language?.trim().toLowerCase();
        if (!songLanguage) {
          return false;
        }

        if (chosenKnownCodes.includes(songLanguage)) {
          return true;
        }

        if (includeOther && !knownLanguageCodes.has(songLanguage)) {
          return true;
        }

        return false;
      }

      return true;
    });
  }, [songs, fromYear, toYear, selectedLanguages]);

  return (
    <div className="min-h-screen bg-green-50">
      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-8 py-8">
        {/* Header with Back to Home */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={onBackToSearch}
            className="flex items-center gap-2 text-gray-600 hover:text-green-600 transition-colors group"
          >
            <Home className="size-5 group-hover:scale-110 transition-transform" />
            <span className="font-medium">Back to Home</span>
          </button>
          
          <h1 
            onClick={onBackToSearch}
            className="text-3xl font-bold bg-gradient-to-r from-green-500 to-emerald-600 bg-clip-text text-transparent cursor-pointer hover:from-green-600 hover:to-emerald-700 transition-all"
          >
            Lyric Search
          </h1>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="mb-6">
          <div className="relative flex items-center">
            <Search className="absolute left-6 size-6 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for a song or lyrics..."
              className="w-full pl-16 pr-32 py-5 text-lg border-2 border-gray-200 rounded-full shadow-lg focus:outline-none focus:border-green-500 focus:shadow-xl transition-all bg-white"
            />
            <button
              type="submit"
              className="absolute right-2 top-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white px-8 py-3 rounded-full font-semibold hover:from-green-600 hover:to-emerald-700 transition-all shadow-md"
            >
              Search
            </button>
          </div>
          <div className="mt-3 flex justify-center items-center gap-3 text-sm font-medium text-gray-700">
            <span className={language === 'en' ? 'text-gray-900' : 'text-gray-500'}>English</span>
            <Switch
              checked={language === 'es'}
              onCheckedChange={(checked: boolean) => setLanguage(checked ? 'es' : 'en')}
              className="data-[state=unchecked]:bg-gray-500 data-[state=checked]:bg-green-600 [&_[data-slot=switch-thumb]]:bg-white"
              aria-label="Toggle search language between English and Spanish"
            />
            <span className={language === 'es' ? 'text-gray-900' : 'text-gray-500'}>Spanish</span>
          </div>
        </form>

        {/* Filters */}
        <div className="mb-6">
          <SearchFilters
            fromYear={fromYear}
            toYear={toYear}
            selectedLanguages={selectedLanguages}
            onYearRangeChange={handleYearRangeChange}
            onLanguageChange={handleLanguageChange}
            onClearAll={handleClearAll}
          />
        </div>

        {/* Results Count */}
        <p className="text-sm text-gray-600 mb-4">
          Found {filteredResults.length} results (0.{Math.floor(Math.random() * 90) + 10} seconds)
        </p>

        {/* Results List */}
        <div className="space-y-4">
          {filteredResults.map((result) => (
            <SearchResult key={result.id} {...result} onSongSelect={onSongSelect} />
          ))}
        </div>

        {/* No Results */}
        {filteredResults.length === 0 && (
          <div className="text-center py-16 bg-white rounded-xl shadow-md">
            <p className="text-lg text-gray-600">No results found for "{searchQuery}"</p>
            <p className="text-sm text-gray-500 mt-2">Try different keywords or adjust your filters</p>
          </div>
        )}

        {/* Pagination */}
        {filteredResults.length > 10 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <button className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-white hover:shadow-md rounded-lg transition-all">
              ‹ Previous
            </button>
            <button className="px-4 py-2 text-sm font-semibold bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg shadow-md">
              1
            </button>
            <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-md rounded-lg transition-all">
              2
            </button>
            <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-md rounded-lg transition-all">
              3
            </button>
            <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-md rounded-lg transition-all">
              4
            </button>
            <span className="px-2 text-gray-500">...</span>
            <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-white hover:shadow-md rounded-lg transition-all">
              10
            </button>
            <button className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-white hover:shadow-md rounded-lg transition-all">
              Next ›
            </button>
          </div>
        )}
      </div>
    </div>
  );
}