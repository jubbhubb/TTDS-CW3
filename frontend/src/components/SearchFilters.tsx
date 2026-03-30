import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { ChevronDown, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";

interface SearchFiltersProps {
  fromYear?: string;
  toYear?: string;
  selectedLanguages: string[];
  onYearRangeChange: (from: string, to: string) => void;
  onLanguageChange: (language: string) => void;
  onClearAll: () => void;
}

export function SearchFilters({
  fromYear,
  toYear,
  selectedLanguages,
  onYearRangeChange,
  onLanguageChange,
  onClearAll,
}: SearchFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1900 + 1 }, (_, i) => 1900 + i).reverse();
  
  // Filter to year options: only show years >= fromYear if fromYear is selected
  const toYearOptions = fromYear && fromYear !== '' 
    ? years.filter(year => year >= parseInt(fromYear))
    : years;
  
  const languages = ['English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Japanese', 'Korean', 'Other'];
  const hasYearRange = Boolean((fromYear && fromYear.trim() !== '') || (toYear && toYear.trim() !== ''));
  const hasActiveFilters = hasYearRange || selectedLanguages.length > 0;

  const totalActiveFilters = (hasYearRange ? 1 : 0) + selectedLanguages.length;

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
                {`${fromYear ?? ''}${fromYear && toYear ? '-' : ''}${toYear ?? ''}`}
                <button
                  onClick={() => onYearRangeChange('', '')}
                  className="hover:bg-green-200 rounded-full p-0.5 transition-colors"
                >
                  <X className="size-3" />
                </button>
              </span>
            )}
            {selectedLanguages.map((language) => (
              <span
                key={language}
                className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full"
              >
                {language}
                <button
                  onClick={() => onLanguageChange(language)}
                  className="hover:bg-green-200 rounded-full p-0.5 transition-colors"
                >
                  <X className="size-3" />
                </button>
              </span>
            ))}
            {/* moods removed */}
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
                        <option key={year} value={year.toString()}>
                          {year}
                        </option>
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
                        <option key={year} value={year.toString()}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Language Filter */}
            <AccordionItem value="language" className="border-gray-200">
              <AccordionTrigger className="py-3 text-sm font-semibold text-gray-900 hover:no-underline">
                Language
                {selectedLanguages.length > 0 && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                    {selectedLanguages.length}
                  </span>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {languages.map((language) => (
                    <label key={language} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded transition-colors">
                      <input
                        type="checkbox"
                        checked={selectedLanguages.includes(language)}
                        onChange={() => onLanguageChange(language)}
                        className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                      />
                      <span className="text-sm text-gray-700">{language}</span>
                    </label>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Mood filter removed */}
          </Accordion>
        </div>
      )}
    </div>
  );
}