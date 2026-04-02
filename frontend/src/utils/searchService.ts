import { getApiPath } from '../config/paths';

export interface SearchResult {
    id: string;
    title: string;
    artist?: string;
    year?: string;
    language?: string;
    snippet?: string;
    score?: number;
    views?: number;
}

export interface SongDetail extends SearchResult {
    author?: string;
    lyrics?: string;
    imageUrl?: string;
    tags?: string;
}

export async function searchQuery(query: string, language: 'en' | 'es' = 'en'): Promise<SearchResult[]> {
    try {
        const params = new URLSearchParams({
            q: query,
            query_language: language,
        });

        const response = await fetch(
            getApiPath(`search?${params.toString()}`),
            {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
            }
        );

        if (!response.ok) {
            throw new Error(`Search failed: ${response.status}`);
        }

        const data = await response.json();
        const results = data.hits || [];

        if (!Array.isArray(results)) {
            return [];
        }

        return results.map((item: any) => ({
            id: item.id?.toString() ?? '',
            title: item.document?.title ?? 'Unknown Title',
            artist: item.document?.artist ?? 'Unknown Artist',
            year: item.document?.year?.toString(),
            language: item.document?.language?.toString(),
            snippet: item.document?.snippet ?? '',
            score: item.score,
            views: item.document?.views
        }));
    } catch (error) {
        console.error('Search error:', error);
        throw error;
    }
}

export async function getSongDetails(songId: string): Promise<SongDetail> {
    try {
        const response = await fetch(
            getApiPath(`documents/${songId}`),
            {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
            }
        );

        if (!response.ok) {
            throw new Error(`Failed to fetch song details: ${response.status}`);
        }

        const data = await response.json();

        return {
            id: data.id?.toString() ?? songId,
            title: data.title ?? 'Unknown Title',
            artist: data.artist ?? 'Unknown Artist',
            author: data.artist ?? 'Unknown Artist',
            year: data.year?.toString(),
            snippet: data.lyrics ? data.lyrics.substring(0, 200) + '...' : '',
            lyrics: data.lyrics ?? '',
            // unexpected fields from backend tailored for frontend if any, otherwise defaults
            tags: data.tag,
            views: data.views
        };
    } catch (error) {
        console.error('Song details error:', error);
        throw error;
    }
}