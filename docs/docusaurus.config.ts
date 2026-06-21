import { themes as prismThemes } from 'prism-react-renderer'
import type { Config } from '@docusaurus/types'
import type * as Preset from '@docusaurus/preset-classic'

const repoUrl = 'https://ghe.megaleo.com/chris-rudnicky/scraper'

const config: Config = {
  title: 'Web Scraper Agent',
  tagline:
    'Dockerized web scraper with Ollama content cleaning and ChromaDB vector memory.',
  favicon: 'img/favicon.png',

  future: {
    v4: true,
  },

  url: 'https://ghe.megaleo.com',
  baseUrl: '/pages/chris-rudnicky/scraper/',

  organizationName: 'chris-rudnicky',
  projectName: 'scraper',
  githubHost: 'ghe.megaleo.com',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          editUrl: `${repoUrl}/edit/main/docs/`,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Web Scraper Agent',
      logo: {
        alt: 'Web Scraper Agent',
        src: 'img/logo.svg',
        href: '/docs/intro',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: repoUrl,
          label: 'Repository',
          position: 'right',
        },
      ],
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'typescript', 'python', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
}

export default config
