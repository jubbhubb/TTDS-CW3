import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { searchQuery as performSearchQuery } from '../utils/searchService';
import { LandingSearch } from './LandingSearch';
import { SearchView } from './SearchView';

interface Song {
    id: string;
    title: string;
    author: string;
    snippet: string;
    year?: string;
    language?: string;
    tag?: string;
    views?: number;
    imageUrl?: string;
}

const Search: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();
    const [songs, setSongs] = useState<Song[]>([]);

    const query = searchParams.get('q') || '';
    const language = searchParams.get('query_language') === 'es' ? 'es' : 'en';

    useEffect(() => {
        if (query) {
            performSearch(query, language);
        }
    }, [query, language]);

    const performSearch = async (searchTerm: string, searchLanguage: 'en' | 'es') => {
        if (!searchTerm.trim()) return;

        try {
            const data = await performSearchQuery(searchTerm, searchLanguage);
            // Transform the API response to match the Song interface
            const transformedData: Song[] = data.map((result) => ({
                id: result.id,
                title: result.title,
                author: result.artist ?? 'Unknown Artist',
                snippet: result.snippet ?? '',
                year: result.year,
                language: result.language,
                tag: result.tag,
                views: result.views,
                imageUrl: undefined
            }));
            setSongs(transformedData);
        } catch (err) {
            console.error(err);
            setSongs([]);
        }
    };

    const handleSearch = (newQuery: string, searchLanguage: 'en' | 'es') => {
        setSearchParams({ q: newQuery, query_language: searchLanguage });
    };

    const handleBackToSearch = () => {
        setSearchParams({});
        setSongs([]);
    };

    const handleSongSelect = (songId: string) => {
        // Navigate to song detail page
        navigate(`/song/${songId}`);
    };

    // Show landing page if no query
    if (!query) {
        return <LandingSearch onSearch={handleSearch} />;
    }

    // Show search results view if there's a query
    return (
        <SearchView
            songs={songs}
            searchQuery={query}
            searchLanguage={language}
            onSearchChange={handleSearch}
            onBackToSearch={handleBackToSearch}
            onSongSelect={handleSongSelect}
        />
    );
};

export default Search;