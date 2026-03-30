import { Music } from "lucide-react";

interface SearchResultProps {
  id: string;
  title: string;
  author: string;
  snippet: string;
  year?: string;
  imageUrl?: string;
  onSongSelect: (songId: string) => void;
}

export function SearchResult({ id, title, author, snippet, year, imageUrl, onSongSelect }: SearchResultProps) {
  return (
    <div 
      onClick={() => onSongSelect(id)}
      className="flex gap-4 bg-white p-5 rounded-xl shadow-md hover:shadow-lg transition-all border border-gray-100 cursor-pointer group"
    >
      {/* Thumbnail */}
      <div className="flex-shrink-0">
        <div className="w-24 h-24 bg-gray-200 rounded-lg overflow-hidden">
          {imageUrl ? (
            <img src={imageUrl} alt={title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-green-400 to-emerald-600">
              <Music className="size-10 text-white" />
            </div>
          )}
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <h3 className="text-xl font-semibold text-green-700 group-hover:text-green-800 group-hover:underline mb-1">
          {title}
        </h3>
        <p className="text-sm text-gray-600 mb-3">
          by <span className="font-medium text-gray-800">{author}</span> {year && `• ${year}`}
        </p>
        <p className="text-sm text-gray-700 leading-relaxed mb-3 line-clamp-3">
          {snippet}
        </p>
        <span className="inline-flex items-center text-sm font-medium text-green-600 group-hover:text-green-700 transition-colors">
          View full lyrics →
        </span>
      </div>
    </div>
  );
}