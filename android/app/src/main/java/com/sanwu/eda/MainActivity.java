package com.sanwu.eda;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;

/**
 * 企业数字助理 · 大屏 Kiosk 壳
 *
 * 职责（薄壳原则）：
 *  1. 全屏横屏 WebView，加载 assets/hud.html（离线演示模式）
 *     或 assets/config.json 里 server_url 指向的电脑端后端（局域网模式）
 *  2. 原生能力桥 AndroidBridge：系统 TTS 朗读 + 系统语音识别
 *     （安卓 WebView 不带 Chrome 的 Web Speech 服务，语音必须走原生桥）
 *  3. Kiosk：常亮、沉浸式全屏、开机自启（BootReceiver）
 */
public class MainActivity extends Activity {

    private WebView web;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private SpeechRecognizer recognizer;
    private String pendingJsResult;   // 识别结果回注给页面的回调名
    private String serverUrl = "";    // 空 = 离线演示模式

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // ---- Kiosk 基础 ----
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideSystemBars();

        readConfig();

        tts = new TextToSpeech(this, status -> ttsReady =
                (status == TextToSpeech.SUCCESS
                 && tts.setLanguage(Locale.SIMPLIFIED_CHINESE) != TextToSpeech.LANG_MISSING_DATA
                 && tts.setLanguage(Locale.SIMPLIFIED_CHINESE) != TextToSpeech.LANG_NOT_SUPPORTED));
        recognizer = SpeechRecognizer.isRecognitionAvailable(this)
                ? SpeechRecognizer.createSpeechRecognizer(this) : null;

        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // 允许自动播报
        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView v, String url) {
                injectShim();   // 页面就绪后注入语音 shim
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources())); // 授权麦克风 getUserMedia
            }
        });

        // 首次进入补请求麦克风权限（部分系统按需弹窗）
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
        }

        web.loadUrl(serverUrl.isEmpty()
                ? "file:///android_asset/hud.html" : serverUrl);
    }

    // ---------- 配置 ----------
    private void readConfig() {
        try {
            AssetManager am = getAssets();
            InputStream in = am.open("config.json");
            byte[] buf = new byte[in.available()];
            in.read(buf); in.close();
            JSONObject cfg = new JSONObject(new String(buf, StandardCharsets.UTF_8));
            serverUrl = cfg.optString("server_url", "").trim();
        } catch (Exception e) {
            // 无配置文件则离线演示模式
        }
    }

    // ---------- 语音 shim：把原生能力伪装成 Web Speech ----------
    private void injectShim() {
        String js =
            "(function(){" +
            " if (!window.speechSynthesis) {" +                    // TTS 降级：走原生桥
            "  window.speechSynthesis = {" +
            "   speak:function(u){ try{ AndroidBridge.speak(u.text||'');" +
            "    var ms=((u.text||'').length)*180;" +
            "    setTimeout(function(){ u.onend && u.onend(); }, ms);}catch(e){} }," +
            "   cancel:function(){ try{AndroidBridge.stopSpeak();}catch(e){} }," +
            "   speaking:function(){return false} };" +
            " }" +
            " if (!window.webkitSpeechRecognition) {" +            // ASR 降级：走原生桥
            "  window.webkitSpeechRecognition = function(){" +
            "   var self=this; this.lang='zh-CN'; this.interimResults=false; this.continuous=false;" +
            "   this.start=function(){ AndroidBridge.recognize(); };" +
            "   this.stop=function(){}; this.abort=function(){};" +
            "   window.__fireAsr = function(text){" +
            "     if(!self.onresult) return;" +
            "     var r=[[{transcript:text}]]; r.length=1;" +
            "     self.onresult({resultIndex:0, results:r});" +
            "     self.onend && self.onend(); };" +
            "  };" +
            " }" +
            "})();";
        web.evaluateJavascript(js, null);
    }

    // ---------- 原生桥 ----------
    private class Bridge {
        @JavascriptInterface
        public void speak(String text) {
            if (ttsReady) tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "eda");
        }
        @JavascriptInterface
        public void stopSpeak() { if (ttsReady) tts.stop(); }

        @JavascriptInterface
        public void recognize() {
            runOnUiThread(() -> {
                if (recognizer == null) {
                    toast("本机无系统语音识别，请用界面文本输入或选择文本意图");
                    return;
                }
                Intent it = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                it.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                it.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN");
                recognizer.setRecognitionListener(new RecognitionListener() {
                    @Override public void onResults(Bundle results) {
                        ArrayList<String> list = results
                                .getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        if (list != null && !list.isEmpty()) {
                            String t = list.get(0).replace("\"", "\\\"");
                            web.evaluateJavascript("window.__fireAsr && window.__fireAsr(\"" + t + "\");", null);
                        }
                    }
                    @Override public void onError(int e) {
                        toast(e == SpeechRecognizer.ERROR_NO_MATCH ? "没听清，再说一遍" : "语音识别不可用(" + e + ")");
                    }
                    @Override public void onReadyForSpeech(Bundle p) {}
                    @Override public void onBeginningOfSpeech() {}
                    @Override public void onRmsChanged(float r) {}
                    @Override public void onBufferReceived(byte[] b) {}
                    @Override public void onEndOfSpeech() {}
                    @Override public void onPartialResults(Bundle p) {}
                    @Override public void onEvent(int t, Bundle p) {}
                });
                recognizer.startListening(it);
            });
        }
    }

    private void toast(String msg) {
        new Handler(Looper.getMainLooper()).post(
                () -> Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show());
    }

    // ---------- Kiosk 沉浸式 ----------
    private void hideSystemBars() {
        View d = getWindow().getDecorView();
        d.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
              | View.SYSTEM_UI_FLAG_FULLSCREEN
              | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
              | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars();
    }

    @Override protected void onDestroy() {
        if (tts != null) { tts.stop(); tts.shutdown(); }
        if (recognizer != null) recognizer.destroy();
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
