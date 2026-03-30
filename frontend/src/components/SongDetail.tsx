import { ArrowLeft, Music, Calendar, User } from "lucide-react";

interface SongDetailProps {
  id: string;
  title: string;
  author: string;
  year?: string;
  imageUrl?: string;
  fullLyrics: string;
  onBack: () => void;
}

export function SongDetail({ title, author, year, imageUrl, fullLyrics, onBack }: SongDetailProps) {
  return (
    <div className="min-h-screen bg-green-50">
      <div className="max-w-4xl mx-auto px-8 py-8">
        {/* Back Button */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-gray-600 hover:text-green-600 transition-colors group mb-8"
        >
          <ArrowLeft className="size-5 group-hover:-translate-x-1 transition-transform" />
          <span className="font-medium">Back to Results</span>
        </button>

        {/* Song Header Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden mb-8">
          <div className="flex flex-col md:flex-row gap-6 p-8">
            {/* Album Art / Thumbnail */}
            <div className="flex-shrink-0">
              <div className="w-48 h-48 rounded-xl overflow-hidden shadow-md">
                {imageUrl ? (
                  <img src={imageUrl} alt={title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-green-400 to-emerald-600">
                    <Music className="size-20 text-white" />
                  </div>
                )}
              </div>
            </div>

            {/* Song Info */}
            <div className="flex-1 flex flex-col justify-center">
              <h1 className="text-4xl font-bold text-gray-900 mb-4">{title}</h1>
              
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-gray-700">
                  <User className="size-5 text-green-600" />
                  <span className="text-lg">
                    <span className="font-semibold">{author}</span>
                  </span>
                </div>
                
                {year && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <Calendar className="size-5 text-green-600" />
                    <span>{year}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Lyrics Section */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 pb-4 border-b border-gray-200">
            Lyrics
          </h2>
          <div className="prose prose-lg max-w-none">
            <pre className="whitespace-pre-wrap font-sans text-gray-700 leading-relaxed">
              {fullLyrics}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
