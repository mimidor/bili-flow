<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="login-hero">
        <div class="login-hero__eyebrow">ARCO DESIGN</div>
        <h1>管理后台登录</h1>
        <p>
          登录后可查看系统监控、内容审核、日志中心，以及内容运营、LLM、量化回测等核心模块。
          当前后台采用统一鉴权和角色权限控制，不同账号会看到不同菜单。
        </p>

        <div class="login-hero__stats">
          <div class="login-stat">
            <span>运维中心</span>
            <strong>监控 / 任务 / 日志</strong>
          </div>
          <div class="login-stat">
            <span>内容运营</span>
            <strong>视频 / 动态 / 推送</strong>
          </div>
          <div class="login-stat">
            <span>权限体系</span>
            <strong>RBAC / 菜单授权</strong>
          </div>
        </div>
      </section>

      <a-card class="login-card" :bordered="false">
        <div class="login-card__header">
          <div>
            <div class="login-card__title">登录</div>
            <div class="login-card__desc">请输入用户名和密码进入后台</div>
          </div>
          <a-tag color="arcoblue">RBAC</a-tag>
        </div>

        <a-alert
          v-if="errorMessage"
          class="login-alert"
          type="error"
          :closable="true"
          @close="errorMessage = ''"
        >
          {{ errorMessage }}
        </a-alert>

        <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
          <a-form-item field="username" label="账号">
            <a-input
              v-model="form.username"
              allow-clear
              placeholder="请输入账号"
              autocomplete="username"
              @keyup.enter="submit"
            />
          </a-form-item>

          <a-form-item field="password" label="密码">
            <a-input-password
              v-model="form.password"
              allow-clear
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </a-form-item>

          <a-button class="login-submit" type="primary" long :loading="loading" @click="submit">
            登录
          </a-button>
        </a-form>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FieldRule, FormInstance } from "@arco-design/web-vue";

import { login } from "../auth";

const router = useRouter();
const route = useRoute();
const formRef = ref<FormInstance>();
const loading = ref(false);
const errorMessage = ref("");

const form = reactive({
  username: "",
  password: "",
});

const rules: Record<string, FieldRule[]> = {
  username: [{ required: true, message: "请输入账号" }],
  password: [{ required: true, message: "请输入密码" }],
};

async function submit() {
  errorMessage.value = "";
  try {
    const errors = await formRef.value?.validate();
    if (errors) return;
  } catch {
    return;
  }

  loading.value = true;
  try {
    await login(form.username.trim(), form.password);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect || "/");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>
