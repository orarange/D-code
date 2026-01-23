import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  // Development server configuration
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    // Proxy WebSocket connections to the Rust backend
    proxy: {
      '/ws': {
        target: 'ws://localhost:9001',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ws/, ''),
      },
    },
  },

  // Preview server (for production builds)
  preview: {
    port: 5173,
    strictPort: true,
  },

  // Build configuration
  build: {
    // Output directory (relative to project root)
    outDir: 'dist',
    // Clear output directory before build
    emptyOutDir: true,
    // Generate source maps for debugging
    sourcemap: process.env.NODE_ENV !== 'production',
    // Target modern browsers
    target: 'esnext',
    // Rollup options
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          // Monaco Editor is large, split it out
          monaco: ['@monaco-editor/react'],
          // React ecosystem
          react: ['react', 'react-dom'],
          // State management
          zustand: ['zustand'],
          // Icons
          icons: ['lucide-react'],
        },
      },
    },
    // Chunk size warnings
    chunkSizeWarningLimit: 1000,
  },

  // Path resolution
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },

  // CSS configuration
  css: {
    // PostCSS is configured via postcss.config.js
    devSourcemap: true,
  },

  // Optimization
  optimizeDeps: {
    // Pre-bundle these dependencies for faster dev server startup
    include: [
      'react',
      'react-dom',
      'zustand',
      'lucide-react',
      '@monaco-editor/react',
      'clsx',
    ],
    // Exclude dependencies that shouldn't be pre-bundled
    exclude: [],
  },

  // Environment variables prefix
  envPrefix: 'DCODE_',

  // Tauri specific configuration
  // When building for Tauri, the dist folder will be bundled into the binary
  clearScreen: false,
});
