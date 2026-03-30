import { Filter, ChevronUp, ChevronDown } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { useState } from "react";

interface DiscoveryPanelProps {
  onArtistFilter: (artist: string) => void;
  onEraFilter: (era: string) => void;
  onSortChange: (direction: "asc" | "desc") => void;
}

export function DiscoveryPanel({ onArtistFilter, onEraFilter, onSortChange }: DiscoveryPanelProps) {
  const [artistInput, setArtistInput] = useState("");
  const [eraInput, setEraInput] = useState("");

  const handleApplyFilters = () => {
    onArtistFilter(artistInput);
    onEraFilter(eraInput);
  };

  return (
    <aside className="w-80 bg-white border-l border-gray-200 p-6 flex flex-col gap-6">
      <div>
        <h3 className="text-lg font-bold mb-4">DISCOVER</h3>
        
        <div className="space-y-4">
          {/* Artist Input */}
          <div>
            <label className="block text-sm font-medium mb-2">Artist</label>
            <Input
              placeholder="Enter artist name..."
              value={artistInput}
              onChange={(e) => setArtistInput(e.target.value)}
              className="w-full"
            />
          </div>

          {/* Era/Time Filter */}
          <div>
            <label className="block text-sm font-medium mb-2">ERA (Time)</label>
            <select
              value={eraInput}
              onChange={(e) => setEraInput(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Eras</option>
              <option value="2020s">2020s</option>
              <option value="2010s">2010s</option>
              <option value="2000s">2000s</option>
              <option value="1990s">1990s</option>
              <option value="classic">Classic</option>
            </select>
          </div>

          {/* Rank by Popularity */}
          <div>
            <label className="block text-sm font-medium mb-2">Rank by Popularity</label>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={() => onSortChange("asc")}
                className="flex-1"
              >
                <ChevronUp className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => onSortChange("desc")}
                className="flex-1"
              >
                <ChevronDown className="size-4" />
              </Button>
            </div>
          </div>

          {/* Apply Filters Button */}
          <Button 
            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white" 
            variant="default"
            onClick={handleApplyFilters}
          >
            <Filter className="size-4 mr-2" />
            Apply Filters
          </Button>
        </div>
      </div>
    </aside>
  );
}