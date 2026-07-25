// vite.config.ts
import { defineConfig } from "file:///E:/PythonProject_Pycharm/FastAPI_project/day_17_%E5%A4%9Aagent/agent%E6%90%AD%E5%BB%BA%E5%B9%B3%E5%8F%B0/web/node_modules/vite/dist/node/index.js";
import react from "file:///E:/PythonProject_Pycharm/FastAPI_project/day_17_%E5%A4%9Aagent/agent%E6%90%AD%E5%BB%BA%E5%B9%B3%E5%8F%B0/web/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "path";
var __vite_injected_original_dirname = "E:\\PythonProject_Pycharm\\FastAPI_project\\day_17_\u591Aagent\\agent\u642D\u5EFA\u5E73\u53F0\\web";
var vite_config_default = defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__vite_injected_original_dirname, "src") }
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-markdown": ["react-markdown", "remark-gfm", "react-syntax-highlighter"],
          "vendor-hot-toast": ["react-hot-toast"],
          "vendor-zustand": ["zustand"]
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true
      },
      // 静态文件(图标/上传文件)
      "/files": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJFOlxcXFxQeXRob25Qcm9qZWN0X1B5Y2hhcm1cXFxcRmFzdEFQSV9wcm9qZWN0XFxcXGRheV8xN19cdTU5MUFhZ2VudFxcXFxhZ2VudFx1NjQyRFx1NUVGQVx1NUU3M1x1NTNGMFxcXFx3ZWJcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIkU6XFxcXFB5dGhvblByb2plY3RfUHljaGFybVxcXFxGYXN0QVBJX3Byb2plY3RcXFxcZGF5XzE3X1x1NTkxQWFnZW50XFxcXGFnZW50XHU2NDJEXHU1RUZBXHU1RTczXHU1M0YwXFxcXHdlYlxcXFx2aXRlLmNvbmZpZy50c1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vRTovUHl0aG9uUHJvamVjdF9QeWNoYXJtL0Zhc3RBUElfcHJvamVjdC9kYXlfMTdfJUU1JUE0JTlBYWdlbnQvYWdlbnQlRTYlOTAlQUQlRTUlQkIlQkElRTUlQjklQjMlRTUlOEYlQjAvd2ViL3ZpdGUuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtyZWFjdCgpXSxcbiAgcmVzb2x2ZToge1xuICAgIGFsaWFzOiB7ICdAJzogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgJ3NyYycpIH0sXG4gIH0sXG4gIGJ1aWxkOiB7XG4gICAgY2h1bmtTaXplV2FybmluZ0xpbWl0OiA4MDAsXG4gICAgcm9sbHVwT3B0aW9uczoge1xuICAgICAgb3V0cHV0OiB7XG4gICAgICAgIG1hbnVhbENodW5rczoge1xuICAgICAgICAgICd2ZW5kb3ItcmVhY3QnOiBbJ3JlYWN0JywgJ3JlYWN0LWRvbScsICdyZWFjdC1yb3V0ZXItZG9tJ10sXG4gICAgICAgICAgJ3ZlbmRvci1tYXJrZG93bic6IFsncmVhY3QtbWFya2Rvd24nLCAncmVtYXJrLWdmbScsICdyZWFjdC1zeW50YXgtaGlnaGxpZ2h0ZXInXSxcbiAgICAgICAgICAndmVuZG9yLWhvdC10b2FzdCc6IFsncmVhY3QtaG90LXRvYXN0J10sXG4gICAgICAgICAgJ3ZlbmRvci16dXN0YW5kJzogWyd6dXN0YW5kJ10sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIHBvcnQ6IDUxNzMsXG4gICAgcHJveHk6IHtcbiAgICAgICcvYXBpJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vMTI3LjAuMC4xOjgwMDEnLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgICAgLy8gXHU5NzU5XHU2MDAxXHU2NTg3XHU0RUY2KFx1NTZGRVx1NjgwNy9cdTRFMEFcdTRGMjBcdTY1ODdcdTRFRjYpXG4gICAgICAnL2ZpbGVzJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vMTI3LjAuMC4xOjgwMDEnLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFrYixTQUFTLG9CQUFvQjtBQUMvYyxPQUFPLFdBQVc7QUFDbEIsT0FBTyxVQUFVO0FBRmpCLElBQU0sbUNBQW1DO0FBSXpDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVMsQ0FBQyxNQUFNLENBQUM7QUFBQSxFQUNqQixTQUFTO0FBQUEsSUFDUCxPQUFPLEVBQUUsS0FBSyxLQUFLLFFBQVEsa0NBQVcsS0FBSyxFQUFFO0FBQUEsRUFDL0M7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLHVCQUF1QjtBQUFBLElBQ3ZCLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQSxRQUNOLGNBQWM7QUFBQSxVQUNaLGdCQUFnQixDQUFDLFNBQVMsYUFBYSxrQkFBa0I7QUFBQSxVQUN6RCxtQkFBbUIsQ0FBQyxrQkFBa0IsY0FBYywwQkFBMEI7QUFBQSxVQUM5RSxvQkFBb0IsQ0FBQyxpQkFBaUI7QUFBQSxVQUN0QyxrQkFBa0IsQ0FBQyxTQUFTO0FBQUEsUUFDOUI7QUFBQSxNQUNGO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxRQUNOLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxNQUNoQjtBQUFBO0FBQUEsTUFFQSxVQUFVO0FBQUEsUUFDUixRQUFRO0FBQUEsUUFDUixjQUFjO0FBQUEsTUFDaEI7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
