import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./styles.css";

document.title = "bili-flow 综合管理后台";

createApp(App).use(createPinia()).use(router).mount("#app");
