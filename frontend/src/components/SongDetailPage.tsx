import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getSongDetails, SongDetail as SongDetailType } from '../utils/searchService';
import { SongDetail } from './SongDetail';

const SongDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [song, setSong] = useState<SongDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSongDetails = async () => {
      if (!id) {
        setError('Song ID is missing');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const songData = await getSongDetails(id);
        setSong(songData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load song details');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchSongDetails();
  }, [id]);

  const handleBack = () => {
    navigate(-1);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-green-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-green-200 border-t-green-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading song details...</p>
        </div>
      </div>
    );
  }

  if (error || !song) {
    return (
      <div className="min-h-screen bg-green-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{error || 'Song not found'}</p>
          <button
            onClick={handleBack}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <SongDetail
      id={song.id?.toString() || ''}
      title={song.title}
      author={song.author || song.artist || 'Unknown Artist'}
      year={song.year}
      imageUrl={song.imageUrl}
      fullLyrics={song.lyrics || 'Lyrics not available'}
      onBack={handleBack}
    />
  );
};

export default SongDetailPage;
