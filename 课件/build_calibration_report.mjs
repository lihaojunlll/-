import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 2) {
    args[argv[i]] = argv[i + 1];
  }
  return args;
}


function parseLog(text) {
  const measurements = [];
  const samples = [];
  const adcSamples = [];
  const adcAverages = [];
  const fits = [];
  const starts = [];
  const dataPattern = /^(motor[12]),(forward|reverse),(-?[\d.]+),([\d.]+),(-?[\d.]+)(?:,(valid|invalid))?$/;
  const samplePattern = /^SAMPLE,(motor[12]),(forward|reverse),(-?[\d.]+),([\d.]+),(\d+),(-?[\d.]+),(-?\d+),(valid|invalid)$/;
  const adcSamplePattern = /^ADC_SAMPLE,(\d+),(adc\d+),(\d+),(-?\d+),(-?[\d.]+),(.+)$/;
  const adcAveragePattern = /^ADC_AVG,(adc\d+),(-?[\d.]+),(-?[\d.]+),(\d+)$/;
  const fitPattern = /^FIT (motor[12]) (forward|reverse): rpm = (-?[\d.]+) \* voltage \+ (-?[\d.]+), R2 = ([\d.]+)$/;
  const startPattern = /^START_VOLTAGE (motor[12]) (forward|reverse): ([\d.]+) V$/;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    let match = line.match(adcSamplePattern);
    if (match) {
      adcSamples.push({
        sampleIndex: Number(match[1]),
        channel: match[2],
        pin: Number(match[3]),
        raw: Number(match[4]),
        voltage: Number(match[5]),
        status: match[6],
      });
      continue;
    }

    match = line.match(adcAveragePattern);
    if (match) {
      adcAverages.push({
        channel: match[1],
        avgRaw: Number(match[2]),
        avgVoltage: Number(match[3]),
        count: Number(match[4]),
      });
      continue;
    }

    match = line.match(samplePattern);
    if (match) {
      samples.push({
        motor: match[1],
        direction: match[2],
        duty: Number(match[3]),
        voltage: Number(match[4]),
        sampleIndex: Number(match[5]),
        rpm: Number(match[6]),
        pulseCount: Number(match[7]),
        status: match[8],
      });
      continue;
    }

    match = line.match(dataPattern);
    if (match) {
      measurements.push({
        motor: match[1],
        direction: match[2],
        duty: Number(match[3]),
        voltage: Number(match[4]),
        rpm: Number(match[5]),
        status: match[6] || "valid",
      });
      continue;
    }

    match = line.match(fitPattern);
    if (match) {
      fits.push({
        motor: match[1],
        direction: match[2],
        slope: Number(match[3]),
        intercept: Number(match[4]),
        rSquared: Number(match[5]),
      });
      continue;
    }

    match = line.match(startPattern);
    if (match) {
      starts.push({
        motor: match[1],
        direction: match[2],
        voltage: Number(match[3]),
      });
    }
  }

  if (measurements.length === 0) {
    throw new Error("No calibration measurements were found in the log.");
  }
  return { measurements, samples, adcSamples, adcAverages, fits, starts };
}


function styleHeader(range, fill = "#1F4E78") {
  range.format = {
    fill,
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#B4C7E7" },
  };
}


function styleBody(range) {
  range.format = {
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
    verticalAlignment: "center",
  };
}


function findFit(fits, motor, direction) {
  return fits.find((item) => item.motor === motor && item.direction === direction) || null;
}


async function buildWorkbook(parsed, outputPath, previewPath) {
  const workbook = Workbook.create();
  const rawSheet = workbook.worksheets.add("原始数据");
  const sampleSheet = workbook.worksheets.add("20次采样明细");
  const adcSheet = workbook.worksheets.add("灰度传感器");
  const fitSheet = workbook.worksheets.add("拟合结果");
  const chartSheet = workbook.worksheets.add("拟合图像");

  rawSheet.showGridLines = false;
  sampleSheet.showGridLines = false;
  adcSheet.showGridLines = false;
  fitSheet.showGridLines = false;
  chartSheet.showGridLines = false;

  rawSheet.getRange("A1:G1").values = [[
    "序号", "电机", "方向", "PWM占空比 (%)", "等效电压 (V)", "实测转速 (RPM)", "数据状态",
  ]];
  const rawRows = parsed.measurements.map((item, index) => [
    index + 1,
    item.motor,
    item.direction,
    item.duty,
    item.voltage,
    item.rpm,
    item.status,
  ]);
  rawSheet.getRangeByIndexes(1, 0, rawRows.length, 7).values = rawRows;
  styleHeader(rawSheet.getRange("A1:G1"));
  styleBody(rawSheet.getRangeByIndexes(1, 0, rawRows.length, 7));
  rawSheet.getRange(`D2:F${rawRows.length + 1}`).format.numberFormat = "0.000";
  rawSheet.getRange("A:G").format.columnWidth = 18;
  rawSheet.getRange("A:A").format.columnWidth = 9;
  rawSheet.freezePanes.freezeRows(1);
  rawSheet.tables.add(`A1:G${rawRows.length + 1}`, true, "CalibrationRawData");

  sampleSheet.getRange("A1:I1").values = [[
    "序号", "电机", "方向", "PWM占空比 (%)", "等效电压 (V)",
    "采样序号", "单次转速 (RPM)", "脉冲数", "数据状态",
  ]];
  const sampleRows = parsed.samples.map((item, index) => [
    index + 1, item.motor, item.direction, item.duty, item.voltage,
    item.sampleIndex, item.rpm, item.pulseCount, item.status,
  ]);
  if (sampleRows.length > 0) {
    sampleSheet.getRangeByIndexes(1, 0, sampleRows.length, 9).values = sampleRows;
    styleBody(sampleSheet.getRangeByIndexes(1, 0, sampleRows.length, 9));
    sampleSheet.tables.add(`A1:I${sampleRows.length + 1}`, true, "CalibrationSamples");
  }
  styleHeader(sampleSheet.getRange("A1:I1"), "#4472C4");
  sampleSheet.getRange("A:I").format.columnWidth = 17;
  sampleSheet.getRange("A:A").format.columnWidth = 9;
  if (sampleRows.length > 0) {
    sampleSheet.getRange(`D2:G${sampleRows.length + 1}`).format.numberFormat = "0.000";
  }
  sampleSheet.freezePanes.freezeRows(1);

  adcSheet.getRange("A1:G1").values = [[
    "序号", "采样序号", "通道", "GPIO", "原始值", "电压 (V)", "状态",
  ]];
  const adcRows = parsed.adcSamples.map((item, index) => [
    index + 1,
    item.sampleIndex,
    item.channel,
    item.pin,
    item.raw,
    item.voltage,
    item.status,
  ]);
  if (adcRows.length > 0) {
    adcSheet.getRangeByIndexes(1, 0, adcRows.length, 7).values = adcRows;
    styleBody(adcSheet.getRangeByIndexes(1, 0, adcRows.length, 7));
    adcSheet.tables.add(`A1:G${adcRows.length + 1}`, true, "PhotoelectricSamples");
    adcSheet.getRange(`E2:F${adcRows.length + 1}`).format.numberFormat = "0.000";
  }
  styleHeader(adcSheet.getRange("A1:G1"), "#548235");
  adcSheet.getRange("A:G").format.columnWidth = 16;
  adcSheet.getRange("A:A").format.columnWidth = 9;
  adcSheet.freezePanes.freezeRows(1);

  adcSheet.getRange("I1:L1").values = [[
    "通道", "平均原始值", "平均电压 (V)", "有效采样数",
  ]];
  const adcAverageRows = parsed.adcAverages.map((item) => [
    item.channel,
    item.avgRaw,
    item.avgVoltage,
    item.count,
  ]);
  if (adcAverageRows.length > 0) {
    adcSheet.getRangeByIndexes(1, 8, adcAverageRows.length, 4).values = adcAverageRows;
    styleBody(adcSheet.getRangeByIndexes(1, 8, adcAverageRows.length, 4));
    adcSheet.getRange(`J2:K${adcAverageRows.length + 1}`).format.numberFormat = "0.000";
    const adcChart = adcSheet.charts.add(
      "bar",
      adcSheet.getRange(`I1:J${adcAverageRows.length + 1}`),
    );
    adcChart.title = "灰度传感器平均原始值";
    adcChart.hasLegend = false;
    adcChart.yAxis = { numberFormatCode: "0" };
    adcChart.setPosition("N1", "U18");
  }
  styleHeader(adcSheet.getRange("I1:L1"), "#70AD47");
  adcSheet.getRange("I:L").format.columnWidth = 17;

  fitSheet.getRange("A1:H1").values = [[
    "电机", "方向", "斜率 (RPM/V)", "截距 (RPM)", "R²",
    "确认起转电压 (V)", "关系式", "反算公式",
  ]];
  const fitRows = parsed.fits.map((item) => {
    const start = parsed.starts.find(
      (value) => value.motor === item.motor && value.direction === item.direction,
    );
    return [
      item.motor,
      item.direction,
      item.slope,
      item.intercept,
      item.rSquared,
      start ? start.voltage : null,
      `rpm = ${item.slope.toFixed(6)} × voltage + ${item.intercept.toFixed(6)}`,
      `voltage = (target_rpm - ${item.intercept.toFixed(6)}) / ${item.slope.toFixed(6)}`,
    ];
  });
  if (fitRows.length > 0) {
    fitSheet.getRangeByIndexes(1, 0, fitRows.length, 8).values = fitRows;
    styleBody(fitSheet.getRangeByIndexes(1, 0, fitRows.length, 8));
    fitSheet.getRange(`C2:F${fitRows.length + 1}`).format.numberFormat = "0.000000";
  } else {
    fitSheet.getRange("A2:H2").merge();
    fitSheet.getRange("A2").values = [[
      "未生成有效拟合：请检查编码器接线、脉冲干扰、ENCODER_CPR 和起转数据。",
    ]];
    fitSheet.getRange("A2:H2").format = {
      fill: "#FCE4D6",
      font: { bold: true, color: "#C00000" },
    };
  }
  styleHeader(fitSheet.getRange("A1:H1"), "#2F75B5");
  fitSheet.getRange("A:B").format.columnWidth = 14;
  fitSheet.getRange("C:F").format.columnWidth = 18;
  fitSheet.getRange("G:H").format.columnWidth = 48;
  fitSheet.getRange("G:H").format.wrapText = true;
  fitSheet.freezePanes.freezeRows(1);

  chartSheet.getRange("A1:J1").merge();
  chartSheet.getRange("A1").values = [["轮子电压-转速标定结果"]];
  chartSheet.getRange("A1:J1").format = {
    fill: "#17365D",
    font: { bold: true, color: "#FFFFFF", size: 18 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    rowHeight: 30,
  };
  chartSheet.getRange("A2:J2").merge();
  chartSheet.getRange("A2").values = [[
    "散点为实测值，直线为线性拟合；电压为供电电压 × PWM占空比的等效平均值。",
  ]];
  chartSheet.getRange("A2:J2").format = {
    fill: "#D9EAF7",
    font: { color: "#1F1F1F", italic: true },
    horizontalAlignment: "center",
  };

  const motors = ["motor1", "motor2"];
  for (let motorIndex = 0; motorIndex < motors.length; motorIndex += 1) {
    const motor = motors[motorIndex];
    const startRow = 4 + motorIndex * 24;
    const data = parsed.measurements.filter((item) => item.motor === motor);
    const voltages = [...new Set(data.map((item) => item.voltage))].sort((a, b) => a - b);
    const forwardFit = findFit(parsed.fits, motor, "forward");
    const reverseFit = findFit(parsed.fits, motor, "reverse");
    const forwardStart = parsed.starts.find(
      (item) => item.motor === motor && item.direction === "forward",
    );
    const reverseStart = parsed.starts.find(
      (item) => item.motor === motor && item.direction === "reverse",
    );

    chartSheet.getRange(`A${startRow}:E${startRow}`).values = [[
      "电压 (V)", "正转实测 RPM", "正转拟合 RPM", "反转实测 RPM", "反转拟合 RPM",
    ]];
    if (voltages.length === 0) {
      chartSheet.getRange(`A${startRow + 1}:E${startRow + 1}`).merge();
      chartSheet.getRange(`A${startRow + 1}`).values = [[
        `${motor} has no motor measurements in this log.`,
      ]];
      styleHeader(chartSheet.getRange(`A${startRow}:E${startRow}`), "#5B9BD5");
      continue;
    }
    const helperRows = voltages.map((voltage) => {
      const forward = data.find(
        (item) => item.direction === "forward" && item.voltage === voltage && item.status === "valid",
      );
      const reverse = data.find(
        (item) => item.direction === "reverse" && item.voltage === voltage && item.status === "valid",
      );
      return [
        voltage,
        forward ? Math.abs(forward.rpm) : null,
        forwardFit && forwardStart && voltage >= forwardStart.voltage
          ? forwardFit.slope * voltage + forwardFit.intercept
          : null,
        reverse ? Math.abs(reverse.rpm) : null,
        reverseFit && reverseStart && voltage >= reverseStart.voltage
          ? reverseFit.slope * voltage + reverseFit.intercept
          : null,
      ];
    });
    chartSheet.getRangeByIndexes(startRow, 0, helperRows.length, 5).values = helperRows;
    styleHeader(chartSheet.getRange(`A${startRow}:E${startRow}`), "#5B9BD5");
    styleBody(chartSheet.getRangeByIndexes(startRow, 0, helperRows.length, 5));
    chartSheet.getRange(`A${startRow + 1}:E${startRow + helperRows.length}`).format.numberFormat = "0.000";
    chartSheet.getRange("A:E").format.columnWidth = 17;

    const chartRange = chartSheet.getRange(
      `A${startRow}:E${startRow + helperRows.length}`,
    );
    const chart = chartSheet.charts.add("line", chartRange);
    chart.title = `${motor === "motor1" ? "左轮 / Motor 1" : "右轮 / Motor 2"} 电压-转速拟合`;
    chart.hasLegend = true;
    chart.xAxis = { numberFormatCode: "0.0" };
    chart.yAxis = { numberFormatCode: "0" };
    chart.xAxis.title.text = "等效电压 (V)";
    chart.yAxis.title.text = "转速绝对值 (RPM)";
    chart.setPosition(`G${startRow}`, `N${startRow + 18}`);
  }

  chartSheet.freezePanes.freezeRows(2);
  chartSheet.getRange("F:F").format.columnWidth = 4;

  const outputDir = path.dirname(outputPath);
  await fs.mkdir(outputDir, { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);

  if (previewPath) {
    const preview = await workbook.render({
      sheetName: "拟合图像",
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  }

  console.log(`REPORT_XLSX=${outputPath}`);
  if (previewPath) {
    console.log(`REPORT_PREVIEW=${previewPath}`);
  }
}


const args = parseArgs(process.argv);
if (!args["--input"] || !args["--output"]) {
  throw new Error(
    "Usage: node build_calibration_report.mjs --input log.txt --output report.xlsx [--preview chart.png]",
  );
}

const logBytes = await fs.readFile(args["--input"]);
let logText;
if (
  logBytes.length >= 2
  && logBytes[0] === 0xff
  && logBytes[1] === 0xfe
) {
  logText = new TextDecoder("utf-16le").decode(logBytes);
} else if (logBytes.includes(0)) {
  logText = new TextDecoder("utf-16le").decode(logBytes);
} else {
  logText = new TextDecoder("utf-8").decode(logBytes);
}
await buildWorkbook(parseLog(logText), args["--output"], args["--preview"]);
