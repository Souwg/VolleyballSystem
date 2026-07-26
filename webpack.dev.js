const webpack = require("webpack");
const path = require("path");
const { merge } = require("webpack-merge");
const common = require("./webpack.common.js");

const port = 3000;
let publicUrl = "auto://0.0.0.0:0/ws";

// only for Gitpod
if (process.env.GITPOD_WORKSPACE_URL) {
  const [schema, host] = process.env.GITPOD_WORKSPACE_URL.split("://");
  publicUrl = `wss://${port}-${host}/ws`;
}

// only for Codespaces
if (process.env.CODESPACE_NAME) {
  publicUrl = `wss://${process.env.CODESPACE_NAME}-${port}.app.github.dev/ws`;
}

module.exports = merge(common, {
  mode: "development",
  devtool: "cheap-module-source-map",

  watchOptions: {
    poll: 1000,
    ignored: /node_modules/,
  },

  devServer: {
    port,
    hot: true,
    allowedHosts: "all",
    historyApiFallback: true,

    static: {
      directory: path.resolve(__dirname, "public"),
      publicPath: "/",
    },

    client: {
      webSocketURL: publicUrl,
    },
  },

  plugins: [new webpack.HotModuleReplacementPlugin()],
});
