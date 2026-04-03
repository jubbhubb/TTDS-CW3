import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { ChevronDown, SlidersHorizontal, X, ArrowUpDown } from "lucide-react";
import { useState } from "react";

const GENRES: { label: string; value: string }[] = [
  { label: 'Pop',     value: 'pop' },
  { label: 'Rap',     value: 'rap' },
  { label: 'Rock',    value: 'rock' },
  { label: 'R&B',     value: 'rb' },
  { label: 'Misc',    value: 'misc' },
  { label: 'Country', value: 'country' },
];


interface SearchFiltersProps {
  fromYear?: string;
  toYear?: string;
  onYearRangeChange: (from: string, to: string) => void;
  selectedGenres: string[];
  onGenreChange: (genre: string) => void;
  viewsSort: 'none' | 'high' | 'low';
  onViewsSortChange: (sort: 'none' | 'high' | 'low') => void;
  onClearAll: () => void;
}

export function SearchFilters({
  fromYear,
  toYear,
  onYearRangeChange,
  selectedGenres,
  onGenreChange,
  viewsSort,
  onViewsSortChange,
  onClearAll,
}: SearchFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1900 + 1 }, (_, i) => 1900 + i).reverse();

  const toYearOptions = fromYear && fromYear !== ''
    ? years.filter(year => year >= parseInt(fromYear))
    : years;

  const hasYearRange = Boolean((fromYear && fromYear.trim() !== '') || (toYear && toYear.trim() !== ''));
  const hasSorting = viewsSort !== 'none';
  const hasActiveFilters = hasYearRange || selectedGenres.length > 0 || hasSorting;
  const totalActiveFilters = (hasYearRange ? 1 : 0) + selectedGenres.length + (hasSorting ? 1 : 0);

  return (
    <div className="w-full">
      {/* Filter Bar */}
      <div className="flex items-center gap-3 mb-4">
        {/* Filters Toggle Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white shadow-sm hover:bg-gray-50 hover:border-gray-400 transition-colors"
        >
          <SlidersHorizontal className="size-4" />
          Filters
          {totalActiveFilters > 0 && (
            <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full font-semibold">
              {totalActiveFilters}
            </span>
          )}
          <ChevronDown className={`size-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Clear All Button */}
        {hasActiveFilters && (
          <button
            onClick={onClearAll}
            className="flex items-center gap-1 px-3 py-2 text-sm text-green-600 hover:text-green-700 font-medium transition-colors"
          >
            <X className="size-4" />
            Clear all
          </button>
        )}

        {/* Active Filter Tags */}
        {hasActiveFilters && (
          <div className="flex items-center gap-2 flex-wrap ml-2">
            {hasYearRange && (
              <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                {`${fromYear ?? ''}${fromYear && toYear ? '–' : ''}${toYear ?? ''}`}
                <button
                  onClick={() => onYearRangeChange('', '')}
                  className="hover:bg-green-200 rounded-full p-0.5 transition-colors"
                >
                  <X className="size-3" />
                </button>
              </span>
            )}
            {selectedGenres.map((g) => {
              const genre = GENRES.find(x => x.value === g);
              return (
                <span key={g} className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                  {genre?.label ?? g}
                  <button
                    onClick={() => onGenreChange(g)}
                    className="hover:bg-green-200 rounded-full p-0.5 transition-colors"
                  >
                    <X className="size-3" />
                  </button>
                </span>
              );
            })}
            {hasSorting && (
              <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                {viewsSort === 'high' ? 'Most popular first' : 'Least popular first'}
                <button
                  onClick={() => onViewsSortChange('none')}
                  className="hover:bg-green-200 rounded-full p-0.5 transition-colors"
                >
                  <X className="size-3" />
                </button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Expandable Filter Panel */}
      {isExpanded && (
        <div className="bg-white p-6 rounded-xl shadow-md border border-gray-200 mb-4">
          <Accordion type="multiple" className="w-full">

            {/* Year Range Filter */}
            <AccordionItem value="year" className="border-gray-200">
              <AccordionTrigger className="py-3 text-sm font-semibold text-gray-900 hover:no-underline">
                Year range
                {hasYearRange && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                    1
                  </span>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <label className="flex flex-col text-sm">
                    <span className="mb-1 text-gray-700">From year</span>
                    <select
                      value={fromYear ?? ''}
                      onChange={(e) => onYearRangeChange(e.target.value, toYear ?? '')}
                      className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
                    >
                      <option value="">Any</option>
                      {years.map((year) => (
                        <option key={year} value={year.toString()}>{year}</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col text-sm">
                    <span className="mb-1 text-gray-700">To year</span>
                    <select
                      value={toYear ?? ''}
                      onChange={(e) => onYearRangeChange(fromYear ?? '', e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 bg-white"
                    >
                      <option value="">Any</option>
                      {toYearOptions.map((year) => (
                        <option key={year} value={year.toString()}>{year}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Genre Filter */}
            <AccordionItem value="genre" className="border-gray-200">
              <AccordionTrigger className="py-3 text-sm font-semibold text-gray-900 hover:no-underline">
                Genre
                {selectedGenres.length > 0 && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                    {selectedGenres.length}
                  </span>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {GENRES.map(({ label, value }) => (
                    <label key={value} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded transition-colors">
                      <input
                        type="checkbox"
                        checked={selectedGenres.includes(value)}
                        onChange={() => onGenreChange(value)}
                        className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                      />
                      <span className="text-sm text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Sort by Views */}
            <AccordionItem value="popularity" className="border-gray-200">
              <AccordionTrigger className="py-3 text-sm font-semibold text-gray-900 hover:no-underline">
                Sort by popularity
                {hasSorting && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                    1
                  </span>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => onViewsSortChange(viewsSort === 'high' ? 'none' : 'high')}
                    className={`flex items-center gap-2 px-4 py-2 text-sm rounded-full border font-medium transition-colors ${
                      viewsSort === 'high'
                        ? 'bg-green-600 text-white border-green-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:border-green-400 hover:text-green-700'
                    }`}
                  >
                    <ArrowUpDown className="size-3" />
                    Most popular first
                  </button>
                  <button
                    onClick={() => onViewsSortChange(viewsSort === 'low' ? 'none' : 'low')}
                    className={`flex items-center gap-2 px-4 py-2 text-sm rounded-full border font-medium transition-colors ${
                      viewsSort === 'low'
                        ? 'bg-green-600 text-white border-green-600'
                        : 'bg-white text-gray-700 border-gray-300 hover:border-green-400 hover:text-green-700'
                    }`}
                  >
                    <ArrowUpDown className="size-3" />
                    Least popular first
                  </button>
                </div>
              </AccordionContent>
            </AccordionItem>

          </Accordion>
        </div>
      )}
    </div>
  );
}
