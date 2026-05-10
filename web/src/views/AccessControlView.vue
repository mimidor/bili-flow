<template>
  <div class="dashboard access-control-page">
    <section class="page-hero">
      <div class="page-hero__copy">
        <div class="page-hero__eyebrow">RBAC / ACCESS CONTROL</div>
        <h1>账号与角色</h1>
        <p class="page-hero__desc">
          管理后台账号、角色和权限映射。第一版按菜单与接口组授权，不做按钮级权限。
        </p>
        <div class="page-hero__chips">
          <span class="page-hero__chip">用户 {{ users.length }}</span>
          <span class="page-hero__chip">角色 {{ roles.length }}</span>
          <span class="page-hero__chip">权限 {{ permissions.length }}</span>
        </div>
      </div>

      <div class="page-hero__panel">
        <div class="page-hero__panel-label">授权模型</div>
        <div class="page-hero__panel-value">RBAC</div>
        <div class="page-hero__panel-note">
          单账号可绑定多个角色，权限取并集。菜单显示和接口访问都由权限控制。
        </div>
      </div>
    </section>

    <el-card class="page-card section">
      <template #header>
        <div class="section-header">
          <div>
            <div class="section__title">权限管理</div>
            <div class="section__desc">账号、角色、权限统一维护</div>
          </div>
          <el-button :loading="loading" @click="loadAll">刷新</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="用户管理" name="users">
          <div class="toolbar">
            <el-input v-model="userQuery" clearable placeholder="搜索用户名 / 显示名 / 角色" style="width: 280px" />
            <el-button type="primary" @click="openUserEditor()">新建用户</el-button>
          </div>

          <el-table :data="filteredUsers" stripe v-loading="loading">
            <el-table-column prop="username" label="用户名" min-width="160" />
            <el-table-column prop="display_name" label="显示名" min-width="160" />
            <el-table-column label="角色" min-width="220">
              <template #default="{ row }">
                <el-space wrap>
                  <el-tag
                    v-for="role in row.roles"
                    :key="role.id"
                    :type="role.code === 'super_admin' ? 'danger' : 'info'"
                  >
                    {{ role.name }}
                  </el-tag>
                </el-space>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "启用" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="超管" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_super_admin ? 'danger' : 'info'">{{ row.is_super_admin ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最近登录" width="180">
              <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-space wrap>
                  <el-button size="small" @click="openUserEditor(row)">编辑</el-button>
                  <el-button size="small" @click="openResetPassword(row)">重置密码</el-button>
                  <el-button size="small" :type="row.is_active ? 'warning' : 'success'" @click="toggleUserActive(row)">
                    {{ row.is_active ? "停用" : "启用" }}
                  </el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="角色管理" name="roles">
          <div class="toolbar">
            <el-input v-model="roleQuery" clearable placeholder="搜索角色编码 / 名称 / 描述" style="width: 280px" />
            <el-button type="primary" @click="openRoleEditor()">新建角色</el-button>
          </div>

          <el-table :data="filteredRoles" stripe v-loading="loading">
            <el-table-column prop="code" label="编码" min-width="140" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="description" label="描述" min-width="240" />
            <el-table-column label="权限数" width="100">
              <template #default="{ row }">{{ row.permission_keys.length }}</template>
            </el-table-column>
            <el-table-column label="用户数" width="100">
              <template #default="{ row }">{{ row.user_count }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? "启用" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="系统角色" width="110">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'warning' : 'info'">{{ row.is_system ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openRoleEditor(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="userEditorVisible" :title="userForm.id ? '编辑用户' : '新建用户'" width="680px">
      <el-form label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="Boolean(userForm.id)" />
        </el-form-item>
        <el-form-item v-if="!userForm.id" label="初始密码">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="userForm.display_name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_ids" multiple filterable style="width: 100%">
            <el-option v-for="role in activeRoles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
        <el-form-item label="超管">
          <el-switch v-model="userForm.is_super_admin" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordVisible" title="重置密码" width="520px">
      <el-form label-width="120px">
        <el-form-item label="用户">
          <el-input :model-value="selectedUser?.username || ''" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="resetPasswordForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPassword" @click="submitResetPassword">重置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleEditorVisible" :title="roleForm.id ? '编辑角色' : '新建角色'" width="860px">
      <el-form label-width="120px">
        <el-form-item label="角色编码">
          <el-input v-model="roleForm.code" :disabled="Boolean(roleForm.id)" />
        </el-form-item>
        <el-form-item label="角色名称">
          <el-input v-model="roleForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="roleForm.is_active" :disabled="roleForm.code === 'super_admin'" />
        </el-form-item>
        <el-form-item label="权限">
          <div class="permission-groups">
            <div v-for="group in permissionGroups" :key="group.key" class="permission-group">
              <div class="permission-group__title">{{ group.name }}</div>
              <el-checkbox-group v-model="roleForm.permission_keys">
                <div class="permission-group__items">
                  <el-checkbox v-for="permission in group.items" :key="permission.key" :label="permission.key">
                    {{ permission.label }}
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRole" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../api";
import type { AdminPermissionItem, AdminRoleItem, AdminUserItem } from "../types";
import { formatDateTime } from "../utils";

type PermissionGroup = {
  key: string;
  name: string;
  items: AdminPermissionItem[];
};

const loading = ref(false);
const savingUser = ref(false);
const savingRole = ref(false);
const savingPassword = ref(false);
const activeTab = ref("users");
const userQuery = ref("");
const roleQuery = ref("");
const users = ref<AdminUserItem[]>([]);
const roles = ref<AdminRoleItem[]>([]);
const permissions = ref<AdminPermissionItem[]>([]);

const userEditorVisible = ref(false);
const passwordVisible = ref(false);
const roleEditorVisible = ref(false);
const selectedUser = ref<AdminUserItem | null>(null);

const userForm = reactive({
  id: null as number | null,
  username: "",
  password: "",
  display_name: "",
  role_ids: [] as number[],
  is_active: true,
  is_super_admin: false,
});

const resetPasswordForm = reactive({
  password: "",
});

const roleForm = reactive({
  id: null as number | null,
  code: "",
  name: "",
  description: "",
  is_active: true,
  permission_keys: [] as string[],
});

const activeRoles = computed(() =>
  roles.value.filter((role) => role.is_active || userForm.role_ids.includes(role.id)),
);

const filteredUsers = computed(() => {
  const query = userQuery.value.trim().toLowerCase();
  if (!query) return users.value;
  return users.value.filter((user) => {
    const haystack = [
      user.username,
      user.display_name || "",
      ...(user.roles || []).map((role) => role.name),
      ...(user.roles || []).map((role) => role.code),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const filteredRoles = computed(() => {
  const query = roleQuery.value.trim().toLowerCase();
  if (!query) return roles.value;
  return roles.value.filter((role) =>
    [role.code, role.name, role.description || ""].join(" ").toLowerCase().includes(query),
  );
});

const permissionGroups = computed<PermissionGroup[]>(() => {
  const groups = new Map<string, PermissionGroup>();
  for (const item of permissions.value) {
    const key = item.group_key || item.kind || "other";
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        name: item.group_name || key,
        items: [],
      });
    }
    groups.get(key)!.items.push(item);
  }
  return Array.from(groups.values()).sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
});

function resetUserForm() {
  userForm.id = null;
  userForm.username = "";
  userForm.password = "";
  userForm.display_name = "";
  userForm.role_ids = [];
  userForm.is_active = true;
  userForm.is_super_admin = false;
}

function resetRoleForm() {
  roleForm.id = null;
  roleForm.code = "";
  roleForm.name = "";
  roleForm.description = "";
  roleForm.is_active = true;
  roleForm.permission_keys = [];
}

async function loadAll() {
  loading.value = true;
  try {
    const [permissionRows, roleRows, userRows] = await Promise.all([
      api.get<AdminPermissionItem[]>("/rbac/permissions"),
      api.get<AdminRoleItem[]>("/rbac/roles"),
      api.get<AdminUserItem[]>("/rbac/users"),
    ]);
    permissions.value = permissionRows;
    roles.value = roleRows;
    users.value = userRows;
  } finally {
    loading.value = false;
  }
}

function openUserEditor(user?: AdminUserItem) {
  if (!user) {
    resetUserForm();
  } else {
    userForm.id = user.id;
    userForm.username = user.username;
    userForm.password = "";
    userForm.display_name = user.display_name || "";
    userForm.role_ids = user.roles.map((role) => role.id);
    userForm.is_active = user.is_active;
    userForm.is_super_admin = user.is_super_admin;
  }
  userEditorVisible.value = true;
}

function openResetPassword(user: AdminUserItem) {
  selectedUser.value = user;
  resetPasswordForm.password = "";
  passwordVisible.value = true;
}

function openRoleEditor(role?: AdminRoleItem) {
  if (!role) {
    resetRoleForm();
  } else {
    roleForm.id = role.id;
    roleForm.code = role.code;
    roleForm.name = role.name;
    roleForm.description = role.description || "";
    roleForm.is_active = role.is_active;
    roleForm.permission_keys = [...role.permission_keys];
  }
  roleEditorVisible.value = true;
}

async function saveUser() {
  if (!userForm.username.trim()) {
    ElMessage.warning("用户名不能为空");
    return;
  }
  if (!userForm.id && !userForm.password.trim()) {
    ElMessage.warning("初始密码不能为空");
    return;
  }
  savingUser.value = true;
  try {
    const payload = {
      username: userForm.username.trim(),
      password: userForm.password,
      display_name: userForm.display_name.trim() || null,
      role_ids: userForm.role_ids,
      is_active: userForm.is_active,
      is_super_admin: userForm.is_super_admin,
    };
    if (userForm.id) {
      await api.put(`/rbac/users/${userForm.id}`, {
        display_name: payload.display_name,
        role_ids: payload.role_ids,
        is_active: payload.is_active,
        is_super_admin: payload.is_super_admin,
      });
    } else {
      await api.post("/rbac/users", payload);
    }
    ElMessage.success("用户已保存");
    userEditorVisible.value = false;
    await loadAll();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    savingUser.value = false;
  }
}

async function toggleUserActive(user: AdminUserItem) {
  const nextActive = !user.is_active;
  await ElMessageBox.confirm(
    `确认${nextActive ? "启用" : "停用"}账号 ${user.username}？`,
    "提示",
    { type: "warning" },
  );
  await api.put(`/rbac/users/${user.id}`, {
    display_name: user.display_name,
    role_ids: user.roles.map((role) => role.id),
    is_active: nextActive,
    is_super_admin: user.is_super_admin,
  });
  ElMessage.success("状态已更新");
  await loadAll();
}

async function submitResetPassword() {
  if (!selectedUser.value) return;
  if (!resetPasswordForm.password.trim()) {
    ElMessage.warning("新密码不能为空");
    return;
  }
  savingPassword.value = true;
  try {
    await api.post(`/rbac/users/${selectedUser.value.id}/reset-password`, {
      password: resetPasswordForm.password,
    });
    ElMessage.success("密码已重置");
    passwordVisible.value = false;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "重置失败");
  } finally {
    savingPassword.value = false;
  }
}

async function saveRole() {
  if (!roleForm.code.trim() && !roleForm.id) {
    ElMessage.warning("角色编码不能为空");
    return;
  }
  if (!roleForm.name.trim()) {
    ElMessage.warning("角色名称不能为空");
    return;
  }
  savingRole.value = true;
  try {
    const payload = {
      code: roleForm.code.trim(),
      name: roleForm.name.trim(),
      description: roleForm.description.trim() || null,
      is_active: roleForm.is_active,
      permission_keys: roleForm.permission_keys,
    };
    if (roleForm.id) {
      await api.put(`/rbac/roles/${roleForm.id}`, {
        name: payload.name,
        description: payload.description,
        is_active: payload.is_active,
        permission_keys: payload.permission_keys,
      });
    } else {
      await api.post("/rbac/roles", payload);
    }
    ElMessage.success("角色已保存");
    roleEditorVisible.value = false;
    await loadAll();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    savingRole.value = false;
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped>
.access-control-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.permission-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.permission-group {
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.34);
}

.permission-group__title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: #dbeafe;
}

.permission-group__items {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

@media (max-width: 768px) {
  .permission-group__items {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
