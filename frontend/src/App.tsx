import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Search from './components/Search';
import SongDetailPage from './components/SongDetailPage';

const App: React.FC = () => {
  return (
        <Routes>
            <Route path="/" element={<Search />} />
            <Route path="/search" element={<Search />} />
            <Route path="/song/:id" element={<SongDetailPage />} />
        </Routes>
  )
}

export default App
