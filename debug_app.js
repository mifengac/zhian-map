// debug_app.js - 零依赖原生的 Chrome DevTools 协议 (CDP) 调试工具
import fs from 'fs';

async function main() {
  console.log("🔍 正在获取 Chrome 浏览器的 WebSocket 调试端点...");
  const res = await fetch('http://127.0.0.1:9222/json/version');
  const metadata = await res.json();
  const wsUrl = metadata.webSocketDebuggerUrl;
  console.log(`🔌 成功连接到 Chrome CDP 服务器: ${wsUrl}`);

  const ws = new WebSocket(wsUrl);

  let id = 1;
  const send = (method, params = {}, sessionId = undefined) => {
    const msgId = id++;
    const payload = { id: msgId, method, params };
    if (sessionId) payload.sessionId = sessionId;
    ws.send(JSON.stringify(payload));
    return new Promise((resolve) => {
      const listener = (event) => {
        const response = JSON.parse(event.data);
        if (response.id === msgId) {
          ws.removeEventListener('message', listener);
          resolve(response.result);
        }
      };
      ws.addEventListener('message', listener);
    });
  };

  ws.onopen = async () => {
    console.log("✅ WebSocket 通道已开启，正在载入测试页面...");

    // 1. 创建指向警情大屏项目的 Chrome 标签页
    console.log("🌐 正在控制浏览器导航到 http://localhost:5007 ...");
    const createTargetResult = await send("Target.createTarget", { url: "http://localhost:5007" });
    const targetId = createTargetResult.targetId;
    console.log(`🎯 调试标签页创建成功，Target ID: ${targetId}`);

    // 2. 附着到页面会话
    const attachResult = await send("Target.attachToTarget", { targetId, flatten: true });
    const sessionId = attachResult.sessionId;
    console.log(`🔑 成功获取会话 Session ID: ${sessionId}`);

    // 3. 启用控制台日志监控与页面事件
    await send("Page.enable", {}, sessionId);
    await send("Runtime.enable", {}, sessionId);

    // 监听浏览器控制台输出并实时打印到终端
    ws.onmessage = (event) => {
      const response = JSON.parse(event.data);
      if (response.method === "Runtime.consoleAPICalled" && response.sessionId === sessionId) {
        const args = response.params.args.map(a => a.value || a.description || JSON.stringify(a)).join(" ");
        console.log(`📢 [浏览器控制台] [${response.params.type.toUpperCase()}]: ${args}`);
      }
    };

    // 4. 等待 6 秒让地图瓦片和离线 JSON 数据完全加载与过渡
    console.log("⏳ 正在等待大屏渲染与瓦片加载 (6 秒)...");
    await new Promise(resolve => setTimeout(resolve, 6000));

    // 5. 抓取当前 Chrome 的渲染截图
    console.log("📸 正在截图以校验地图显示效果...");
    const screenshotResult = await send("Page.captureScreenshot", { format: "png" }, sessionId);
    const base64Data = screenshotResult.data;

    const outputPath = "screenshot.png";
    fs.writeFileSync(outputPath, Buffer.from(base64Data, 'base64'));
    console.log(`🎉 调试截图抓取完成！图片已成功保存到: ${outputPath}`);

    // 6. 关闭新建的测试标签页，关闭 WebSocket
    console.log("🧹 正在清理关闭测试页...");
    await send("Target.closeTarget", { targetId });
    ws.close();
  };
}

main().catch(err => {
  console.error("❌ 调试脚本发生异常:", err);
});
