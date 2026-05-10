import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { ArcoResolver } from "unplugin-vue-components/resolvers";

const allowedHosts = [
  "461i36u103.goho.co",
  ".goho.co",
  ".trycloudflare.com",
  "mimidor.xyz",
  ".mimidor.xyz",
  "localhost",
  "127.0.0.1",
];

const legacyElementComponents = new Set([
  "ElAlert",
  "ElButton",
  "ElCard",
  "ElCheckbox",
  "ElCheckboxGroup",
  "ElCollapse",
  "ElCollapseItem",
  "ElDatePicker",
  "ElDescriptions",
  "ElDescriptionsItem",
  "ElDialog",
  "ElDivider",
  "ElDrawer",
  "ElEmpty",
  "ElForm",
  "ElFormItem",
  "ElIcon",
  "ElInput",
  "ElInputNumber",
  "ElLink",
  "ElOption",
  "ElPagination",
  "ElPopconfirm",
  "ElProgress",
  "ElRadioButton",
  "ElRadioGroup",
  "ElScrollbar",
  "ElSkeleton",
  "ElSelect",
  "ElSpace",
  "ElSwitch",
  "ElTable",
  "ElTableColumn",
  "ElTabPane",
  "ElTabs",
  "ElTag",
]);

function LegacyElementResolver(componentName: string) {
  if (!legacyElementComponents.has(componentName)) return;
  return {
    name: componentName,
    from: "element-plus",
    sideEffects: "element-plus/dist/index.css",
  };
}

export default defineConfig({
  plugins: [
    vue(),
    Components({
      dts: "src/components.d.ts",
      resolvers: [ArcoResolver({ importStyle: "css" }), LegacyElementResolver],
    }),
  ],
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;

          if (id.includes("pdfjs-dist")) return "pdf";
          if (id.includes("xterm")) return "terminal";
          if (id.includes("echarts")) return "charts";
          if (id.includes("markdown-it") || id.includes("highlight.js") || id.includes("katex")) return "richtext";
          if (id.includes("naive-ui")) return "naive";
          if (id.includes("@arco-design")) return "arco";
          if (id.includes("element-plus")) return "element";
          if (id.includes("@vue") || id.includes("vue-router") || id.includes("pinia")) return "framework";

          return "vendor";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    allowedHosts,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
