"use client";

import { useState } from "react";
import { Cloud, LoaderCircle, Plus, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";

import { useSettingsStore } from "../store";

export function ExternalImageCard() {
  const config = useSettingsStore((state) => state.config);
  const isLoadingConfig = useSettingsStore((state) => state.isLoadingConfig);
  const isSavingConfig = useSettingsStore((state) => state.isSavingConfig);
  const setExternalImageField = useSettingsStore((state) => state.setExternalImageField);
  const setExternalImageModel = useSettingsStore((state) => state.setExternalImageModel);
  const removeExternalImageModel = useSettingsStore((state) => state.removeExternalImageModel);
  const saveConfig = useSettingsStore((state) => state.saveConfig);

  const [newAlias, setNewAlias] = useState("");
  const [newUpstream, setNewUpstream] = useState("");

  if (isLoadingConfig || !config?.external_image) {
    return (
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="flex items-center justify-center p-10">
          <LoaderCircle className="size-5 animate-spin text-stone-400" />
        </CardContent>
      </Card>
    );
  }

  const external = config.external_image;
  const models = Object.entries(external.external_models || {});

  const handleAdd = () => {
    const alias = newAlias.trim();
    const upstream = newUpstream.trim() || alias;
    if (!alias) {
      return;
    }
    setExternalImageModel(alias, upstream);
    setNewAlias("");
    setNewUpstream("");
  };

  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-stone-900">
              <Cloud className="size-5 text-stone-500" />
              外部图片服务
            </div>
            <p className="mt-1 text-xs leading-6 text-stone-500">
              把指定模型名的生图请求转发到第三方 OpenAI 兼容接口。命中映射的模型不占用本机账号池，
              适合补充本机没有能力的模型（例如 gpt-image-2.5）。
            </p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs ${external.enabled ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
            {external.enabled ? "已启用" : "未启用"}
          </span>
        </div>

        <div className="space-y-4 rounded-xl border border-stone-200 bg-white px-4 py-3">
          <label className="flex items-center gap-3 text-sm text-stone-700">
            <Checkbox
              checked={Boolean(external.enabled)}
              onCheckedChange={(checked) => setExternalImageField("enabled", Boolean(checked))}
            />
            启用外部图片服务
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm text-stone-700">接口地址</label>
              <Input
                value={external.base_url}
                onChange={(event) => setExternalImageField("base_url", event.target.value)}
                placeholder="https://image.example.com"
                className="h-10 rounded-xl border-stone-200 bg-white"
              />
              <p className="text-xs leading-5 text-stone-500">不要带结尾斜杠，会自动补 /v1/images/...</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm text-stone-700">API Key</label>
              <Input
                type="password"
                value={external.api_key || ""}
                onChange={(event) => setExternalImageField("api_key", event.target.value)}
                placeholder={external.has_api_key ? "已保存，留空则不修改" : "sk-..."}
                className="h-10 rounded-xl border-stone-200 bg-white"
              />
              <p className="text-xs leading-5 text-stone-500">
                {external.has_api_key ? "已保存密钥；留空保存将沿用原密钥。" : "密钥仅保存在本机 config.json。"}
              </p>
            </div>
          </div>

          <div className="space-y-2 sm:w-1/2">
            <label className="text-sm text-stone-700">超时（秒）</label>
            <Input
              value={String(external.timeout_sec ?? 180)}
              onChange={(event) => setExternalImageField("timeout_sec", Number(event.target.value) || 180)}
              placeholder="180"
              className="h-10 rounded-xl border-stone-200 bg-white"
            />
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-stone-200 bg-white px-4 py-3">
          <div className="text-sm font-medium text-stone-700">模型映射</div>
          <p className="text-xs leading-5 text-stone-500">
            左侧是暴露给 /v1/models 和调用方使用的模型名，右侧是转发给第三方的真实模型名。
          </p>

          {models.length > 0 ? (
            <div className="space-y-2">
              {models.map(([alias, upstream]) => (
                <div key={alias} className="flex items-center gap-2">
                  <Input
                    value={alias}
                    readOnly
                    className="h-9 flex-1 rounded-lg border-stone-200 bg-stone-50 font-mono text-xs"
                  />
                  <span className="text-stone-400">→</span>
                  <Input
                    value={upstream}
                    onChange={(event) => setExternalImageModel(alias, event.target.value)}
                    className="h-9 flex-1 rounded-lg border-stone-200 bg-white font-mono text-xs"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-9 shrink-0 text-stone-400 hover:text-red-600"
                    onClick={() => removeExternalImageModel(alias)}
                    title={`删除 ${alias}`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-stone-400">尚未配置任何模型映射</p>
          )}

          <div className="flex flex-col gap-2 border-t border-stone-100 pt-3 sm:flex-row sm:items-center">
            <Input
              value={newAlias}
              onChange={(event) => setNewAlias(event.target.value)}
              placeholder="对外模型名，如 gpt-image-2.5"
              className="h-9 flex-1 rounded-lg border-stone-200 bg-white font-mono text-xs"
            />
            <span className="hidden text-stone-400 sm:inline">→</span>
            <Input
              value={newUpstream}
              onChange={(event) => setNewUpstream(event.target.value)}
              placeholder="上游模型名（留空同左）"
              className="h-9 flex-1 rounded-lg border-stone-200 bg-white font-mono text-xs"
            />
            <Button
              variant="outline"
              className="h-9 shrink-0 rounded-lg"
              onClick={handleAdd}
              disabled={!newAlias.trim()}
            >
              <Plus className="size-4" />
              添加
            </Button>
          </div>
        </div>

        <div className="flex justify-end">
          <Button className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800" onClick={() => void saveConfig()} disabled={isSavingConfig}>
            {isSavingConfig ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            保存
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
