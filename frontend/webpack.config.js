const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const { DefinePlugin } = require("webpack");

const API_TARGET = process.env.API_TARGET || "http://localhost:8000";

module.exports = (_env, argv) => {
  const prod = argv.mode === "production";
  return {
    entry: "./src/index.jsx",
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: prod ? "js/[name].[contenthash:8].js" : "js/[name].js",
      publicPath: "/",
      clean: true,
    },
    resolve: { extensions: [".js", ".jsx"] },
    devtool: prod ? "source-map" : "eval-cheap-module-source-map",
    module: {
      rules: [
        { test: /\.jsx?$/, exclude: /node_modules/, use: "babel-loader" },
        {
          test: /\.css$/,
          use: [prod ? MiniCssExtractPlugin.loader : "style-loader", "css-loader"],
        },
        { test: /\.(png|svg|jpe?g|gif)$/i, type: "asset/resource", generator: { filename: "img/[hash][ext]" } },
      ],
    },
    plugins: [
      new DefinePlugin({ "process.env.API_BASE": JSON.stringify(process.env.API_BASE || "/api") }),
      new HtmlWebpackPlugin({ template: "./public/index.html", favicon: "./public/favicon.svg" }),
      ...(prod ? [new MiniCssExtractPlugin({ filename: "css/[name].[contenthash:8].css" })] : []),
    ],
    optimization: {
      splitChunks: {
        cacheGroups: {
          vendor: { test: /[\\/]node_modules[\\/]/, name: "vendor", chunks: "all" },
        },
      },
    },
    performance: { hints: false },
    devServer: {
      port: 3000,
      host: "0.0.0.0",
      hot: true,
      historyApiFallback: true,
      proxy: [{ context: ["/api"], target: API_TARGET, changeOrigin: true }],
    },
  };
};
