#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_camera.h"
#include "esp_err.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "app_config.h"
#include "camera/camera_vision.h"

static const char *TAG = "camera";

#define FIRMWARE_UI_VERSION "bend-slowdown-v5"

static const char INDEX_HTML[] =
    "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>ESP32-S3 Grayscale Camera</title>"
    "<style>body{margin:0;font-family:Arial,sans-serif;background:#111;color:#eee;text-align:center}"
    "header{padding:14px;background:#1d1d1d}.dual{display:flex;gap:10px;justify-content:center;align-items:flex-start;flex-wrap:wrap;padding:10px}"
    ".panel{position:relative;display:inline-block;border:2px solid #333;border-radius:6px;overflow:hidden;background:#000}"
    ".panel .title{position:absolute;top:4px;left:8px;z-index:20;background:rgba(0,0,0,.7);color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}"
    "img,canvas{display:block;max-width:40vw;height:auto}"
    "canvas{pointer-events:none}"
    ".status{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;max-width:760px;margin:12px auto;text-align:left}"
    ".box{background:#1d1d1d;border:1px solid #333;border-radius:6px;padding:10px}.label{color:#aaa;font-size:12px}.value{font-size:20px;font-weight:700}"
    ".turn-left{color:#ffcc33}.turn-right{color:#55b8ff}.turn-straight{color:#8ee66f}.turn-lost{color:#ff6666}"
    "a,button{display:inline-block;margin:10px;padding:10px 14px;border-radius:6px;background:#2d7df6;color:white;text-decoration:none;border:0}"
    ".wrap{padding:12px}</style></head><body>"
    "<header><h2>ESP32-S3 Bend Assist</h2></header>"
    "<div class='dual'>"
    "<div class='panel'><div class='title'>Camera</div><img id='view' src='/jpg'></div>"
    "<div class='panel'><div class='title'>Detection</div><canvas id='detect'></canvas></div>"
    "</div>"
    "<div class='status'>"
    "<div class='box'><div class='label'>Bend</div><div class='value' id='turn'>WAIT</div></div>"
    "<div class='box'><div class='label'>Slowdown Assist</div><div class='value' id='slow'>0.00</div></div>"
    "<div class='box'><div class='label'>Confidence</div><div class='value' id='quality'>0.00</div></div>"
    "<div class='box'><div class='label'>Ahead Curve</div><div class='value' id='curve'>0.00</div></div>"
    "<div class='box'><div class='label'>Near / Far / Look</div><div class='value' id='rows'>--</div></div>"
    "<div class='box'><div class='label'>Fit points</div><div class='value' id='fitcount'>--</div></div>"
    "<div class='box'><div class='label'>Black samples</div><div class='value' id='black'>--</div></div>"
    "</div>"
    "<p><a href='/jpg' target='_blank'>Open Snapshot</a>"
    "<button onclick=\"setSnapshotMode()\">Snapshot Mode</button></p>"
    "<p>Connect to Wi-Fi: S3CAM, then open http://192.168.4.1/</p>"
    "<p style='color:#777;font-size:12px'>Firmware: " FIRMWARE_UI_VERSION "</p>"
    "<script>"
    "let snapshotTimer=null,snapshotActive=false,snapshotBusy=false;"
    "function scheduleSnapshot(delay){if(snapshotActive)snapshotTimer=setTimeout(refreshSnapshot,delay)}"
    "function refreshSnapshot(){if(!snapshotActive||snapshotBusy)return;snapshotBusy=true;document.getElementById('view').src='/jpg?t='+Date.now()}"
    "function setSnapshotMode(){snapshotActive=true;if(snapshotTimer)clearTimeout(snapshotTimer);refreshSnapshot()}"
    "function f(x){return Number(x).toFixed(2)}"
    "function px(v,w){return ((Number(v)+1)*0.5)*w}"
    "function py(v,h,fh){return fh?Number(v)*h/fh:0}"
    "function drawDetection(s){let c=document.getElementById('detect');"
    "if(!s.frame_width)return;"
    "let cw=360,ch=s.frame_height*360/s.frame_width;c.width=cw;c.height=ch;"
    "let sx=cw/s.frame_width,sy=ch/s.frame_height;"
    "let ctx=c.getContext('2d');"
    "ctx.fillStyle='#1a1a1a';ctx.fillRect(0,0,cw,ch);"
    "let rows=[['look',s.look,s.look_y],['far',s.far,s.far_y],['mid',s.mid,s.mid_y],['near',s.near,s.near_y]],keyRows=[['near',s.near,s.near_y],['mid',s.mid,s.mid_y],['far',s.far,s.far_y],['look',s.look,s.look_y]],fit=s.fit||[];"
    "let valid=fit.filter(p=>p.q>0.01);"
    "ctx.save();ctx.globalAlpha=0.4;ctx.strokeStyle='#555';ctx.lineWidth=1;ctx.setLineDash([4,4]);"
    "for(let r of rows){let y=r[2]*sy;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(cw,y);ctx.stroke();}"
    "ctx.setLineDash([]);ctx.restore();"
    "ctx.save();ctx.strokeStyle='rgba(85,184,255,.22)';ctx.lineWidth=1;"
    "for(let p of fit){let y=p.y*sy;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(cw,y);ctx.stroke();}"
    "ctx.restore();"
    "for(let r of rows){let y=r[2]*sy;ctx.fillStyle='#f0f0f0';ctx.fillRect(0,y-2,cw,4);}"
    "ctx.save();ctx.shadowBlur=0;"
    "for(let p of fit){let a=p.q>0.01?(0.35+Math.min(1,p.q)*0.55):0.18;ctx.beginPath();ctx.arc(px(p.x,cw),p.y*sy,4+Math.min(1,p.q)*3,0,6.283);ctx.fillStyle='rgba(85,184,255,'+a+')';ctx.fill();ctx.lineWidth=1;ctx.strokeStyle='rgba(255,255,255,.55)';ctx.stroke();}"
    "ctx.restore();"
    "ctx.lineWidth=7;ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=s.turn<0?'#ffcc33':(s.turn>0?'#55b8ff':'#8ee66f');ctx.shadowColor='#000';ctx.shadowBlur=10;"
    "let ordered=valid.slice().sort((a,b)=>b.y-a.y);"
    "let path=ordered.length>=2?ordered.map(p=>[px(p.x,cw),p.y*sy,p.q]):keyRows.map(r=>[px(r[1],cw),r[2]*sy,1]);"
    "let pts=[[px(0,cw),ch-2,1]].concat(path);"
    "ctx.beginPath();for(let i=0;i<pts.length;i++){if(i===0)ctx.moveTo(pts[i][0],pts[i][1]);else ctx.lineTo(pts[i][0],pts[i][1]);}ctx.stroke();"
    "ctx.shadowBlur=0;ctx.beginPath();ctx.arc(px(0,cw),ch-2,7,0,6.283);ctx.fillStyle='#fff';ctx.fill();ctx.lineWidth=3;ctx.strokeStyle='#8ee66f';ctx.stroke();"
    "for(let i=0;i<rows.length;i++){let cx_px=px(rows[i][1],cw),cy_px=rows[i][2]*sy;ctx.shadowBlur=12;ctx.beginPath();ctx.arc(cx_px,cy_px,10,0,6.283);ctx.fillStyle='#000';ctx.fill();ctx.lineWidth=3;ctx.strokeStyle='#fff';ctx.stroke();ctx.beginPath();ctx.arc(cx_px,cy_px,5,0,6.283);ctx.fillStyle=s.turn<0?'#ffcc33':(s.turn>0?'#55b8ff':'#8ee66f');ctx.fill();}"
    "ctx.shadowBlur=0;ctx.font='11px Arial';ctx.fillStyle='#fff';ctx.textAlign='center';"
    "for(let r of rows){let cx_px=px(r[1],cw),cy_px=r[2]*sy;ctx.fillText(f(r[1]),cx_px,cy_px-14);}"
    "let blk=s.near_black+'/'+s.far_black+'/'+s.look_black;ctx.font='10px Arial';ctx.fillStyle='#aaa';"
    "ctx.fillText('black: '+blk,cw/2,ch-6);}"
    "let img=document.getElementById('view');img.onload=function(){snapshotBusy=false;scheduleSnapshot(80)};img.onerror=function(){snapshotBusy=false;scheduleSnapshot(250)};"
    "async function poll(){try{let r=await fetch('/status',{cache:'no-store'});let s=await r.json();"
    "let t=document.getElementById('turn');t.className='value ';"
    "if(s.age_ms>1000){t.textContent='LOST';t.className+='turn-lost'}"
    "else if(s.turn<0){t.textContent='LEFT';t.className+='turn-left'}"
    "else if(s.turn>0){t.textContent='RIGHT';t.className+='turn-right'}"
    "else{t.textContent='CLEAR';t.className+='turn-straight'}"
    "document.getElementById('slow').textContent=f(s.slowdown);"
    "document.getElementById('quality').textContent=f(s.quality);"
    "document.getElementById('curve').textContent=f(s.curve);"
    "document.getElementById('rows').textContent=f(s.near)+','+f(s.far)+','+f(s.look);"
    "document.getElementById('fitcount').textContent=(s.fit?s.fit.length:0)+' / 13';"
    "document.getElementById('black').textContent=s.near_black+'/'+s.near_samples+' '+s.mid_black+'/'+s.mid_samples+' '+s.far_black+'/'+s.far_samples+' '+s.look_black+'/'+s.look_samples;"
    "drawDetection(s);"
    "}catch(e){document.getElementById('turn').textContent='ERR'}setTimeout(poll,100)}setSnapshotMode();poll();"
    "</script>"
    "</div></body></html>";

static esp_err_t index_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
    return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

static void set_no_cache_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
    httpd_resp_set_hdr(req, "Pragma", "no-cache");
    httpd_resp_set_hdr(req, "Expires", "0");
}

static esp_err_t jpg_handler(httpd_req_t *req)
{
    int64_t start_us = esp_timer_get_time();
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == NULL) {
        ESP_LOGE(TAG, "Camera capture failed");
        return httpd_resp_send_500(req);
    }

    httpd_resp_set_type(req, "image/jpeg");
    set_no_cache_headers(req);
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    esp_err_t res;
    uint8_t *jpg_buf = NULL;
    size_t jpg_len = 0;

    if (fb->format == PIXFORMAT_JPEG) {
        res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
        jpg_len = fb->len;
    } else if (frame2jpg(fb, CAMERA_STREAM_JPEG_QUALITY, &jpg_buf, &jpg_len)) {
        res = httpd_resp_send(req, (const char *)jpg_buf, jpg_len);
        free(jpg_buf);
    } else {
        ESP_LOGE(TAG, "JPEG conversion failed");
        res = httpd_resp_send_500(req);
    }

    ESP_LOGI(TAG, "jpg %ux%u %u bytes %" PRId64 "ms",
             fb->width, fb->height, jpg_len,
             (esp_timer_get_time() - start_us) / 1000);
    esp_camera_fb_return(fb);
    return res;
}

static esp_err_t stream_handler(httpd_req_t *req)
{
    char part_buf[96];
    bool first_frame = true;

    esp_err_t res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
    if (res != ESP_OK) {
        return res;
    }
    set_no_cache_headers(req);

    while (true) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == NULL) {
            ESP_LOGW(TAG, "Camera capture failed, retrying");
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        uint8_t *jpg_buf = NULL;
        size_t jpg_len = fb->len;
        const uint8_t *jpg_data = fb->buf;
        if (fb->format != PIXFORMAT_JPEG) {
            if (!frame2jpg(fb, CAMERA_STREAM_JPEG_QUALITY, &jpg_buf, &jpg_len)) {
                ESP_LOGW(TAG, "JPEG conversion failed, skipping frame");
                esp_camera_fb_return(fb);
                vTaskDelay(pdMS_TO_TICKS(50));
                continue;
            }
            jpg_data = jpg_buf;
        }

        if (jpg_len == 0) {
            ESP_LOGW(TAG, "Empty JPEG frame, skipping");
            if (jpg_buf != NULL) free(jpg_buf);
            esp_camera_fb_return(fb);
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        if (first_frame) {
            res = httpd_resp_send_chunk(req, "--frame\r\n", 8);
            first_frame = false;
        } else {
            res = httpd_resp_send_chunk(req, "\r\n--frame\r\n", 10);
        }
        if (res != ESP_OK) break;

        size_t header_len = snprintf(part_buf, sizeof(part_buf),
                                     "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                                     jpg_len);
        res = httpd_resp_send_chunk(req, part_buf, header_len);
        if (res != ESP_OK) break;

        res = httpd_resp_send_chunk(req, (const char *)jpg_data, jpg_len);

        if (jpg_buf != NULL) {
            free(jpg_buf);
        }
        esp_camera_fb_return(fb);

        if (res != ESP_OK) {
            ESP_LOGI(TAG, "Stream client disconnected");
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(CAMERA_STREAM_DELAY_MS));
    }
    return res;
}

static esp_err_t status_handler(httpd_req_t *req)
{
    camera_vision_state_t state;
    camera_vision_get_state(&state);

    int64_t now_us = esp_timer_get_time();
    int age_ms = state.update_us > 0 ? (int)((now_us - state.update_us) / 1000) : 999999;

    char json[1536];
    int len = snprintf(json, sizeof(json),
                       "{"
                       "\"seq\":%d,"
                       "\"age_ms\":%d,"
                       "\"frame_width\":%d,"
                       "\"frame_height\":%d,"
                       "\"near\":%.3f,"
                       "\"mid\":%.3f,"
                       "\"far\":%.3f,"
                       "\"look\":%.3f,"
                       "\"near_y\":%d,"
                       "\"mid_y\":%d,"
                       "\"far_y\":%d,"
                       "\"look_y\":%d,"
                       "\"curve\":%.3f,"
                       "\"quality\":%.3f,"
                       "\"turn\":%d,"
                       "\"slowdown\":%.3f,"
                       "\"near_black\":%d,"
                       "\"near_samples\":%d,"
                       "\"mid_black\":%d,"
                       "\"mid_samples\":%d,"
                       "\"far_black\":%d,"
                       "\"far_samples\":%d,"
                       "\"look_black\":%d,"
                       "\"look_samples\":%d,"
                       "\"fw\":\"" FIRMWARE_UI_VERSION "\","
                       "\"fit\":[",
                       state.seq, age_ms,
                       state.frame_width, state.frame_height,
                       state.near_x, state.mid_x, state.far_x, state.look_x,
                       state.near_y, state.mid_y, state.far_y, state.look_y,
                       state.curve, state.quality, state.turn, state.slowdown,
                       state.near_black, state.near_samples,
                       state.mid_black, state.mid_samples,
                       state.far_black, state.far_samples,
                       state.look_black, state.look_samples);

    int fit_count = state.fit_count;
    if (fit_count > CAMERA_VISION_FIT_POINTS) {
        fit_count = CAMERA_VISION_FIT_POINTS;
    }
    for (int i = 0; i < fit_count && len < (int)sizeof(json); i++) {
        len += snprintf(json + len, sizeof(json) - len,
                        "%s{\"x\":%.3f,\"y\":%d,\"q\":%.3f}",
                        i > 0 ? "," : "",
                        state.fit_x[i], state.fit_y[i], state.fit_quality[i]);
    }
    if (len < (int)sizeof(json)) {
        len += snprintf(json + len, sizeof(json) - len, "]}");
    }
    if (len >= (int)sizeof(json)) {
        len = sizeof(json) - 1;
        json[len] = '\0';
    }

    httpd_resp_set_type(req, "application/json");
    set_no_cache_headers(req);
    return httpd_resp_send(req, json, len);
}

void camera_web_init(camera_config_t *config)
{
    esp_err_t err = esp_camera_init(config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_camera_init failed: 0x%x", err);
        return;
    }

    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor != NULL) {
        ESP_LOGI(TAG, "sensor PID=0x%02x VER=0x%02x MIDL=0x%02x MIDH=0x%02x",
                 sensor->id.PID, sensor->id.VER, sensor->id.MIDL, sensor->id.MIDH);
        int effect_ret = sensor->set_special_effect(sensor, 2);
        int saturation_ret = sensor->set_saturation(sensor, -2);
        sensor->set_brightness(sensor, 0);
        sensor->set_contrast(sensor, 2);
        sensor->set_gain_ctrl(sensor, 0);
        sensor->set_exposure_ctrl(sensor, 0);
        sensor->set_aec_value(sensor, 400);
        sensor->set_agc_gain(sensor, 0);
        sensor->set_hmirror(sensor, 1);
        sensor->set_vflip(sensor, 0);
        ESP_LOGI(TAG, "force grayscale: special_effect=%d saturation=%d contrast=2 aec=400 hmirror=1",
                 effect_ret, saturation_ret);
    }
    ESP_LOGI(TAG, "Camera initialized");

    httpd_config_t http_cfg = HTTPD_DEFAULT_CONFIG();
    http_cfg.server_port = 80;
    http_cfg.ctrl_port = 32768;
    http_cfg.stack_size = 8192;
    http_cfg.lru_purge_enable = true;

    httpd_handle_t server = NULL;
    ESP_ERROR_CHECK(httpd_start(&server, &http_cfg));

    httpd_uri_t index_uri = { .uri = "/", .method = HTTP_GET, .handler = index_handler };
    httpd_uri_t jpg_uri   = { .uri = "/jpg", .method = HTTP_GET, .handler = jpg_handler };
    httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler };
    httpd_uri_t status_uri = { .uri = "/status", .method = HTTP_GET, .handler = status_handler };

    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &index_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &jpg_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &stream_uri));
    ESP_ERROR_CHECK(httpd_register_uri_handler(server, &status_uri));
    ESP_LOGI(TAG, "HTTP camera server started");
}
